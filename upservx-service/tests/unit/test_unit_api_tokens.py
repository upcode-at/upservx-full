"""Security and lifecycle tests for revocable, scoped API tokens."""

import json
import stat

import pytest

from lib import api_tokens
from lib.permissions import check_api_token_capability, check_api_token_permission


@pytest.fixture()
def token_store(tmp_path, monkeypatch):
    store = tmp_path / "api_tokens.json"
    lock = tmp_path / "api_tokens.lock"
    monkeypatch.setattr(api_tokens, "API_TOKENS_FILE", str(store))
    monkeypatch.setattr(api_tokens, "API_TOKENS_LOCK_FILE", str(lock))
    return store, lock


def test_token_plaintext_is_returned_once_and_only_a_hash_is_stored(token_store):
    store, lock = token_store

    token, metadata = api_tokens.create_api_token(
        "automation", "operator", ["containers:read", "containers:write"]
    )
    persisted = json.loads(store.read_text())

    assert token.startswith("upx_")
    assert token not in store.read_text()
    assert persisted["tokens"][0]["token_hash"] == api_tokens._token_hash(token)
    assert "token_hash" not in metadata
    assert "token_hash" not in api_tokens.list_api_tokens()[0]
    assert stat.S_IMODE(store.stat().st_mode) == 0o600
    assert stat.S_IMODE(lock.stat().st_mode) == 0o600


def test_token_verification_roles_scopes_and_revocation(token_store):
    token, metadata = api_tokens.create_api_token(
        "container deployer", "operator", ["containers:*"]
    )
    principal = api_tokens.verify_api_token(token)

    assert principal is not None
    assert check_api_token_permission(principal, "/containers", "GET") is True
    assert check_api_token_permission(principal, "/containers", "POST") is True
    assert check_api_token_permission(principal, "/security/packages", "GET") is False
    assert check_api_token_permission(principal, "/unknown", "GET") is False
    assert check_api_token_capability(principal, "shell:access") is False

    assert api_tokens.revoke_api_token(metadata["id"]) is True
    assert api_tokens.verify_api_token(token) is None
    assert api_tokens.revoke_api_token("missing") is False


@pytest.mark.parametrize(
    ("role", "scopes", "method", "path", "allowed"),
    [
        ("admin", {"admin:write"}, "POST", "/security/packages/upgrade", True),
        ("admin", {"admin:read"}, "POST", "/security/packages/upgrade", False),
        ("operator", {"admin:*"}, "GET", "/security/packages", False),
        ("read-only", {"containers:*"}, "GET", "/containers", True),
        ("read-only", {"containers:*"}, "POST", "/containers", False),
        ("read-only", {"cluster:read"}, "GET", "/cluster/health", True),
        ("read-only", {"cluster:*"}, "GET", "/cluster/info", True),
        ("read-only", {"cluster:write"}, "POST", "/cluster/create", False),
        ("admin", {"*"}, "POST", "/cluster/ha/heartbeat", False),
    ],
)
def test_role_and_scope_are_both_required(role, scopes, method, path, allowed):
    principal = api_tokens.ApiTokenPrincipal(
        token_id="test",
        name="test",
        role=role,
        scopes=frozenset(scopes),
        expires_at=None,
    )
    assert check_api_token_permission(principal, path, method) is allowed


def test_expired_and_malformed_token_records_fail_closed(token_store, monkeypatch):
    store, _ = token_store
    token, _ = api_tokens.create_api_token(
        "short lived", "admin", ["*"], expires_in=300
    )
    created_at = int(api_tokens.time.time())
    monkeypatch.setattr(api_tokens.time, "time", lambda: created_at + 301)
    assert api_tokens.verify_api_token(token) is None

    store.write_text('{"tokens": "not-a-list"}')
    with pytest.raises(RuntimeError, match="Invalid API token store"):
        api_tokens.verify_api_token(token)


@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_api_tokens_cannot_access_raw_host_configuration(method):
    principal = api_tokens.ApiTokenPrincipal(
        token_id="test",
        name="admin automation",
        role="admin",
        scopes=frozenset({"*"}),
        expires_at=None,
    )
    assert (
        check_api_token_permission(
            principal,
            "/proxy/configs/example.com/advanced",
            method,
        )
        is False
    )


def test_legacy_global_key_is_hashed_and_removed_from_settings(token_store, tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"api_key": "legacy-secret", "monitoring": True}))

    assert api_tokens.migrate_legacy_api_key(settings) is True

    migrated_settings = json.loads(settings.read_text())
    assert migrated_settings == {"monitoring": True}
    assert "legacy-secret" not in token_store[0].read_text()
    principal = api_tokens.verify_api_token("legacy-secret")
    assert principal is not None
    assert principal.role == "admin"
    assert principal.scopes == frozenset({"*"})
