"""Unit tests for signed, replay-safe cluster transport."""

import json
import os
import time
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from lib import cluster_security
from lib.cluster_security import (
    HEADER_NONCE,
    ClusterSecurityError,
    NodeTLSMaterial,
    cluster_url,
    create_bootstrap_response,
    derive_key_id,
    ensure_node_tls,
    install_rotated_child_key,
    load_cluster_keyring,
    normalize_cluster_port,
    sign_cluster_headers,
    signed_cluster_request_sync,
    verify_bootstrap_response,
    verify_cluster_signature,
)


TEST_KEY = "cluster-secret-with-at-least-thirty-two-bytes"
TEST_NODE = "node-a"
TEST_NONCE = "nonce_value_1234567890"


@pytest.fixture()
def isolated_security_paths(monkeypatch, tmp_path):
    security_dir = tmp_path / "cluster-security"
    config_dir = tmp_path / "config"
    monkeypatch.setattr(cluster_security, "CLUSTER_SECURITY_DIR", security_dir)
    monkeypatch.setattr(cluster_security, "NODE_CA_CERT_FILE", security_dir / "node-ca.pem")
    monkeypatch.setattr(cluster_security, "NODE_CA_KEY_FILE", security_dir / "node-ca.key")
    monkeypatch.setattr(cluster_security, "NODE_CERT_FILE", security_dir / "node.pem")
    monkeypatch.setattr(cluster_security, "NODE_KEY_FILE", security_dir / "node.key")
    monkeypatch.setattr(cluster_security, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(cluster_security, "MASTER_CONFIG_FILE", config_dir / "master")
    monkeypatch.setattr(cluster_security, "CHILD_CONFIG_FILE", config_dir / "child")
    monkeypatch.setattr(cluster_security, "NODES_DIR", config_dir / "nodes")
    monkeypatch.setattr(cluster_security, "NONCE_CACHE_FILE", config_dir / "nonces.json")
    monkeypatch.setattr(cluster_security, "NONCE_LOCK_FILE", config_dir / "nonces.lock")
    return security_dir, config_dir


def _signed_headers(*, method="POST", target="/cluster/ha/heartbeat", body=b"{}", now=1_700_000_000):
    return sign_cluster_headers(
        TEST_KEY,
        method,
        target,
        body,
        node_id=TEST_NODE,
        timestamp=now,
        nonce=TEST_NONCE,
    )


def test_cluster_urls_are_https_only_and_legacy_ports_are_upgraded():
    assert normalize_cluster_port(9500) == cluster_security.CLUSTER_TLS_PORT
    assert normalize_cluster_port(9555) == 9555
    assert cluster_url("10.0.0.5", 9500, "/cluster/info") == (
        f"https://10.0.0.5:{cluster_security.CLUSTER_TLS_PORT}/cluster/info"
    )
    assert cluster_url("2001:db8::1", 9555, "/cluster/info") == (
        "https://[2001:db8::1]:9555/cluster/info"
    )


@pytest.mark.parametrize("host", ["http://node-a", "node-a/path", ""])
def test_cluster_url_rejects_unsafe_hosts(host):
    with pytest.raises(ClusterSecurityError):
        cluster_url(host, 9501, "/cluster/info")


def test_valid_signature_authenticates_exact_request():
    now = 1_700_000_000
    body = b'{"priority":100}'
    target = "/cluster/ha/heartbeat?source=node-a"
    headers = _signed_headers(target=target, body=body, now=now)

    verified = verify_cluster_signature(
        "POST",
        target,
        body,
        headers,
        keyring={derive_key_id(TEST_KEY): TEST_KEY},
        now=now,
        check_replay=False,
        check_peer=False,
    )

    assert verified.node_id == TEST_NODE
    assert verified.key_id == derive_key_id(TEST_KEY)
    assert verified.nonce == TEST_NONCE


@pytest.mark.parametrize(
    ("method", "target", "body"),
    [
        ("GET", "/cluster/ha/heartbeat", b"{}"),
        ("POST", "/cluster/ha/vote", b"{}"),
        ("POST", "/cluster/ha/heartbeat", b'{"changed":true}'),
    ],
)
def test_signature_rejects_method_target_and_body_tampering(method, target, body):
    now = 1_700_000_000
    headers = _signed_headers(now=now)
    with pytest.raises(ClusterSecurityError, match="Invalid cluster request signature"):
        verify_cluster_signature(
            method,
            target,
            body,
            headers,
            keyring={derive_key_id(TEST_KEY): TEST_KEY},
            now=now,
            check_replay=False,
            check_peer=False,
        )


@pytest.mark.parametrize("offset", [-61, 61])
def test_signature_rejects_requests_outside_clock_window(offset):
    now = 1_700_000_000
    headers = _signed_headers(now=now + offset)
    with pytest.raises(ClusterSecurityError, match="allowed window"):
        verify_cluster_signature(
            "POST",
            "/cluster/ha/heartbeat",
            b"{}",
            headers,
            keyring={derive_key_id(TEST_KEY): TEST_KEY},
            now=now,
            check_replay=False,
            check_peer=False,
        )


def test_signature_rejects_unknown_key_and_incomplete_headers():
    now = 1_700_000_000
    headers = _signed_headers(now=now)
    with pytest.raises(ClusterSecurityError, match="Unknown or expired"):
        verify_cluster_signature(
            "POST",
            "/cluster/ha/heartbeat",
            b"{}",
            headers,
            keyring={},
            now=now,
            check_replay=False,
            check_peer=False,
        )

    incomplete = dict(headers)
    incomplete.pop(HEADER_NONCE)
    with pytest.raises(ClusterSecurityError, match="Incomplete"):
        verify_cluster_signature(
            "POST",
            "/cluster/ha/heartbeat",
            b"{}",
            incomplete,
            keyring={derive_key_id(TEST_KEY): TEST_KEY},
            now=now,
            check_replay=False,
            check_peer=False,
        )


def test_nonce_is_accepted_once_across_persistent_cache(isolated_security_paths):
    now = 1_700_000_000
    headers = _signed_headers(now=now)
    kwargs = {
        "keyring": {derive_key_id(TEST_KEY): TEST_KEY},
        "now": now,
        "check_peer": False,
    }

    verify_cluster_signature(
        "POST",
        "/cluster/ha/heartbeat",
        b"{}",
        headers,
        **kwargs,
    )
    with pytest.raises(ClusterSecurityError, match="Replayed"):
        verify_cluster_signature(
            "POST",
            "/cluster/ha/heartbeat",
            b"{}",
            headers,
            **kwargs,
        )


def test_keyring_loads_current_pending_and_unexpired_previous_keys(
    isolated_security_paths,
):
    _, config_dir = isolated_security_paths
    config_dir.mkdir()
    now = int(time.time())
    master_config = {
        "key": "current-key",
        "pending_key": {"key": "pending-key"},
        "previous_keys": [
            {"key": "still-valid", "valid_until": now + 60},
            {"key": "expired", "valid_until": now - 1},
            {"key": "malformed", "valid_until": "never"},
        ],
    }
    (config_dir / "master").write_text(json.dumps(master_config), encoding="utf-8")

    keyring = load_cluster_keyring()

    assert set(keyring.values()) == {"current-key", "pending-key", "still-valid"}


def test_child_key_rotation_keeps_old_key_during_overlap(isolated_security_paths):
    _, config_dir = isolated_security_paths
    config_dir.mkdir()
    old_key = "old-cluster-key"
    (config_dir / "child").write_text(
        json.dumps({"cluster_key": old_key, "previous_keys": []}),
        encoding="utf-8",
    )
    new_key = "new-cluster-key-with-at-least-thirty-two-bytes"
    valid_until = int(time.time()) + 300

    install_rotated_child_key(new_key, derive_key_id(new_key), valid_until)

    config = json.loads((config_dir / "child").read_text(encoding="utf-8"))
    assert os.stat(config_dir / "child").st_mode & 0o777 == 0o600
    assert config["cluster_key"] == new_key
    assert config["cluster_key_id"] == derive_key_id(new_key)
    assert config["previous_keys"] == [
        {
            "key_id": derive_key_id(old_key),
            "key": old_key,
            "valid_until": valid_until,
        }
    ]


def test_tls_material_is_generated_with_private_key_permissions(isolated_security_paths):
    material = ensure_node_tls()

    assert "BEGIN CERTIFICATE" in material.ca_certificate
    assert Path(material.cert_file).exists()
    assert Path(material.key_file).exists()
    assert os.stat(material.key_file).st_mode & 0o777 == 0o600
    assert os.stat(cluster_security.NODE_CA_KEY_FILE).st_mode & 0o777 == 0o600
    assert ensure_node_tls() == material


def test_bootstrap_response_is_nonce_bound_and_authenticated(
    isolated_security_paths,
    monkeypatch,
):
    material = ensure_node_tls()
    monkeypatch.setattr(cluster_security, "get_local_node_id", lambda: TEST_NODE)
    now = 1_700_000_000
    payload = create_bootstrap_response(TEST_KEY, TEST_NONCE, timestamp=now)

    ca, node_id, port = verify_bootstrap_response(
        TEST_KEY,
        payload,
        TEST_NONCE,
        expected_node_id=TEST_NODE,
        now=now,
    )
    assert ca == material.ca_certificate
    assert node_id == TEST_NODE
    assert port == cluster_security.CLUSTER_TLS_PORT

    payload["proof"] = "0" * 64
    with pytest.raises(ClusterSecurityError, match="bootstrap proof"):
        verify_bootstrap_response(
            TEST_KEY,
            payload,
            TEST_NONCE,
            now=now,
        )


def test_signed_client_rejects_plain_http_before_network_access(
    isolated_security_paths,
):
    material = ensure_node_tls()
    with pytest.raises(ClusterSecurityError, match="Unencrypted"):
        signed_cluster_request_sync(
            "GET",
            "http://node-a:9500/cluster/info",
            key=TEST_KEY,
            node_id=TEST_NODE,
            ca_certificate=material.ca_certificate,
        )


def test_inter_node_call_sites_do_not_contain_plain_http_urls():
    service_root = Path(__file__).resolve().parents[2]
    for relative_path in (
        "api/cluster.py",
        "lib/ha_manager.py",
        "lib/container_sync.py",
    ):
        source = (service_root / relative_path).read_text(encoding="utf-8")
        assert "http://" not in source


def test_cluster_info_schema_never_exposes_cluster_token():
    from api.cluster import ClusterInfo

    schema = ClusterInfo(is_master=True, is_member=True, nodes=[]).model_dump()
    assert "cluster_token" not in schema
    assert "token" not in schema


def test_registration_model_rejects_path_traversal_as_node_identity():
    from pydantic import ValidationError

    from api.cluster import NodeRegistrationRequest

    with pytest.raises(ValidationError):
        NodeRegistrationRequest(
            hostname="../../etc/cron.d/peer",
            ip_address="10.0.0.2",
            port=9501,
            tls_ca_certificate="not-validated-until-registration",
        )


def test_cluster_debug_redacts_current_pending_and_previous_keys():
    from api.cluster import _redact_cluster_secrets

    redacted = _redact_cluster_secrets(
        {
            "key": "current-secret",
            "pending_key": {"key": "pending-secret", "key_id": "pending-id"},
            "previous_keys": [{"key": "old-secret", "key_id": "old-id"}],
            "cluster_key": "child-secret",
        }
    )

    serialized = json.dumps(redacted)
    assert "current-secret" not in serialized
    assert "pending-secret" not in serialized
    assert "old-secret" not in serialized
    assert "child-secret" not in serialized
    assert redacted["pending_key"]["key_id"] == "pending-id"


@pytest.mark.asyncio
async def test_master_key_rotation_updates_peers_before_committing_new_key():
    from api.cluster import ClusterKeyRotationRequest, rotate_cluster_key

    old_key = "old-master-cluster-key"
    master_config = {
        "key": old_key,
        "key_id": derive_key_id(old_key),
        "previous_keys": [],
    }
    writes = []
    response = MagicMock(status_code=200)
    peer = {
        "hostname": "node-b",
        "ip_address": "10.0.0.2",
        "port": 9501,
        "tls_ca_certificate": "pinned-ca",
    }

    with (
        patch("api.cluster.is_master_node", return_value=True),
        patch("api.cluster.read_master_config", return_value=master_config),
        patch("api.cluster.write_master_config", side_effect=lambda value: writes.append(deepcopy(value))),
        patch("api.cluster.list_all_nodes", return_value=[peer]),
        patch("api.cluster.get_hostname", return_value="node-a"),
        patch(
            "api.cluster._resolve_peer_tls",
            new=AsyncMock(return_value=("pinned-ca", 9501, "node-b")),
        ),
        patch(
            "api.cluster.signed_cluster_request",
            new=AsyncMock(return_value=response),
        ) as signed_request,
    ):
        result = await rotate_cluster_key(ClusterKeyRotationRequest(overlap_seconds=300))

    assert len(writes) == 2
    assert "pending_key" in writes[0]
    assert writes[-1]["key"] == result["token"]
    assert writes[-1]["key_id"] == result["key_id"]
    assert writes[-1]["previous_keys"][0]["key"] == old_key
    assert "pending_key" not in writes[-1]
    assert result["updated_nodes"] == ["node-b"]
    assert signed_request.await_args.kwargs["key"] == old_key
    assert signed_request.await_args.args[1].startswith("https://")


@pytest.mark.asyncio
async def test_master_key_rotation_stays_pending_when_a_peer_does_not_acknowledge():
    from api.cluster import ClusterKeyRotationRequest, rotate_cluster_key

    old_key = "old-master-cluster-key"
    master_config = {"key": old_key, "previous_keys": []}
    writes = []
    peer = {
        "hostname": "node-b",
        "ip_address": "10.0.0.2",
        "port": 9501,
        "tls_ca_certificate": "pinned-ca",
    }

    with (
        patch("api.cluster.is_master_node", return_value=True),
        patch("api.cluster.read_master_config", return_value=master_config),
        patch("api.cluster.write_master_config", side_effect=lambda value: writes.append(deepcopy(value))),
        patch("api.cluster.list_all_nodes", return_value=[peer]),
        patch("api.cluster.get_hostname", return_value="node-a"),
        patch(
            "api.cluster._resolve_peer_tls",
            new=AsyncMock(side_effect=ClusterSecurityError("offline", 503)),
        ),
    ):
        with pytest.raises(HTTPException) as error:
            await rotate_cluster_key(ClusterKeyRotationRequest(overlap_seconds=300))

    assert error.value.status_code == 503
    assert len(writes) == 1
    assert writes[0]["key"] == old_key
    assert "pending_key" in writes[0]
