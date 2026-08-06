"""Integration checks for the HTTP authorization middleware."""

from unittest.mock import patch

import httpx
import pytest
from fastapi.routing import APIRoute

from lib.cluster_security import VerifiedClusterRequest
from lib.api_tokens import ApiTokenPrincipal
from lib.permissions import has_route_policy


async def _request(app, method, path, *, base_url="http://testserver", **kwargs):
    """Issue an ASGI request without TestClient's worker thread."""

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url=base_url,
    ) as client:
        return await client.request(method, path, **kwargs)


def test_every_registered_api_route_has_an_explicit_policy(app):
    """A new FastAPI route must fail CI until its authorization is classified."""

    missing = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if method not in {"HEAD", "OPTIONS"} and not has_route_policy(
                method,
                route.path,
            ):
                missing.append(f"{method} {route.path}")

    assert missing == []


@pytest.mark.asyncio
async def test_unknown_route_is_denied_even_for_api_key(app, api_key_headers):
    response = await _request(
        app,
        "GET",
        "/route-that-does-not-exist",
        headers=api_key_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_wrong_method_is_denied_before_router_dispatch(app, api_key_headers):
    response = await _request(
        app,
        "GET",
        "/security/packages/upgrade",
        headers=api_key_headers,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "scopes", "method", "path"),
    [
        ("operator", {"admin:*"}, "GET", "/security/packages"),
        ("read-only", {"admin:*"}, "POST", "/security/packages/upgrade"),
        ("admin", {"admin:read"}, "POST", "/security/packages/upgrade"),
        ("admin", {"containers:*"}, "POST", "/cluster/create"),
    ],
)
async def test_api_token_role_and_scope_denials_are_enforced(
    app, role, scopes, method, path
):
    principal = ApiTokenPrincipal(
        token_id="limited",
        name="Limited token",
        role=role,
        scopes=frozenset(scopes),
        expires_at=None,
    )
    with patch("main.verify_api_token", return_value=principal):
        response = await _request(
            app,
            method,
            path,
            headers={"Authorization": "Bearer limited-token"},
            json={} if method != "GET" else None,
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_revoked_or_unknown_api_token_is_rejected(app):
    with (
        patch("main.verify_api_token", return_value=None),
        patch("main.verify_session_token", return_value=None),
    ):
        response = await _request(
            app,
            "GET",
            "/security/packages",
            headers={"Authorization": "Bearer revoked-token"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_api_token_cannot_replace_a_signed_cluster_peer(app):
    principal = ApiTokenPrincipal(
        token_id="admin",
        name="Administrator token",
        role="admin",
        scopes=frozenset({"*"}),
        expires_at=None,
    )
    with patch("main.verify_api_token", return_value=principal):
        response = await _request(
            app,
            "POST",
            "/cluster/ha/heartbeat",
            headers={"Authorization": "Bearer admin-token"},
            json={},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_regular_user_cannot_read_security_routes(app):
    with (
        patch("main.verify_session_token", return_value="alice"),
        patch("main.get_user_groups", return_value=set()),
    ):
        response = await _request(
            app,
            "GET",
            "/security/packages",
            headers={"Authorization": "Bearer session-token"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_container_operator_cannot_mutate_security_routes(app):
    with (
        patch("main.verify_session_token", return_value="operator"),
        patch("main.get_user_groups", return_value={"docker"}),
    ):
        response = await _request(
            app,
            "POST",
            "/security/packages/upgrade",
            headers={"Authorization": "Bearer session-token"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_vm_operator_cannot_create_cluster(app):
    with (
        patch("main.verify_session_token", return_value="operator"),
        patch("main.get_user_groups", return_value={"libvirt"}),
    ):
        response = await _request(
            app,
            "POST",
            "/cluster/create",
            headers={"Authorization": "Bearer session-token"},
            json={"cluster_name": "forbidden"},
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_legacy_cluster_bearer_secret_is_rejected(app):
    response = await _request(
        app,
        "GET",
        "/cluster/node/metrics",
        headers={"Authorization": "Bearer legacy-cluster-secret"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_signature_fails_closed_even_with_valid_api_key(
    app,
    api_key_headers,
):
    headers = {
        **api_key_headers,
        "X-Upcode-Harbor-Signature": "invalid",
    }
    response = await _request(
        app,
        "GET",
        "/security/packages",
        base_url="https://testserver:9501",
        headers=headers,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cluster_listener_rejects_browser_and_api_token_traffic(
    app,
    api_key_headers,
):
    response = await _request(
        app,
        "GET",
        "/jobs",
        base_url="https://testserver:9501",
        headers=api_key_headers,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_signed_cluster_transport_is_rejected_on_plain_http(app):
    verified = VerifiedClusterRequest(
        node_id="node-a",
        key_id="key-id",
        timestamp=1_700_000_000,
        nonce="nonce_value_1234567890",
    )
    with patch("main.verify_cluster_signature", return_value=verified) as verifier:
        response = await _request(
            app,
            "GET",
            "/cluster/ha/vote",
            headers={"X-Upcode-Harbor-Signature": "would-otherwise-be-valid"},
        )

    assert response.status_code == 400
    verifier.assert_not_called()


@pytest.mark.asyncio
async def test_signed_cluster_principal_cannot_call_admin_or_management_routes(app):
    verified = VerifiedClusterRequest(
        node_id="node-a",
        key_id="key-id",
        timestamp=1_700_000_000,
        nonce="nonce_value_1234567890",
    )
    signature_headers = {"X-Upcode-Harbor-Signature": "verified-by-test-double"}
    with patch("main.verify_cluster_signature", return_value=verified):
        security_response = await _request(
            app,
            "GET",
            "/security/packages",
            base_url="https://testserver:9501",
            headers=signature_headers,
        )
        cluster_admin_response = await _request(
            app,
            "POST",
            "/cluster/ha/failover",
            base_url="https://testserver:9501",
            headers=signature_headers,
            json={"reason": "forbidden"},
        )
        container_write_response = await _request(
            app,
            "POST",
            "/containers",
            base_url="https://testserver:9501",
            headers=signature_headers,
            json={},
        )

    assert security_response.status_code == 403
    assert cluster_admin_response.status_code == 403
    assert container_write_response.status_code == 403


@pytest.mark.asyncio
async def test_signed_cluster_principal_can_reach_only_internal_routes(app):
    verified = VerifiedClusterRequest(
        node_id="node-a",
        key_id="key-id",
        timestamp=1_700_000_000,
        nonce="nonce_value_1234567890",
    )
    with (
        patch("main.verify_cluster_signature", return_value=verified),
        patch("api.ha.get_ha_manager") as get_ha_manager,
    ):
        get_ha_manager.return_value.get_status.return_value = {
            "hostname": "node-b",
            "my_hostname": "node-b",
            "my_ip": "10.0.0.2",
            "priority": 100,
        }
        response = await _request(
            app,
            "GET",
            "/cluster/ha/vote",
            base_url="https://testserver:9501",
            headers={"X-Upcode-Harbor-Signature": "verified-by-test-double"},
        )

    assert response.status_code == 200
