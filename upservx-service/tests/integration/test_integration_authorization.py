"""Integration checks for the HTTP authorization middleware."""

from unittest.mock import patch

import httpx
import pytest
from fastapi.routing import APIRoute

from lib.permissions import has_route_policy


async def _request(app, method, path, **kwargs):
    """Issue an ASGI request without TestClient's worker thread."""

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
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
async def test_cluster_principal_cannot_call_admin_or_management_routes(app):
    with patch("api.cluster.get_cluster_key", return_value="cluster-token"):
        security_response = await _request(
            app,
            "GET",
            "/security/packages",
            headers={"Authorization": "Bearer cluster-token"},
        )
        cluster_admin_response = await _request(
            app,
            "POST",
            "/cluster/ha/failover",
            headers={"Authorization": "Bearer cluster-token"},
            json={"reason": "forbidden"},
        )
        container_write_response = await _request(
            app,
            "POST",
            "/containers",
            headers={"Authorization": "Bearer cluster-token"},
            json={},
        )

    assert security_response.status_code == 403
    assert cluster_admin_response.status_code == 403
    assert container_write_response.status_code == 403
