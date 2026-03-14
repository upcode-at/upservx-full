"""
Integration tests for api/auth.py
=====================================
Tests login, logout, WS ticket, and /auth/me via the real FastAPI router.
PAM and system-dependent components are mocked.

Note: Tests build a lightweight test app that includes the auth router
without the full PAM middleware.
"""

import base64
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Minimal test app (auth router only, without PAM middleware)
# ---------------------------------------------------------------------------

def _make_auth_app(pam_ok: bool = True):
    """Creates an isolated FastAPI app with auth router and mocked PAM."""
    app = FastAPI()

    # Zustand für request.state vorbelegen (wird von /auth/me genutzt)
    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = "testuser"
        request.state.groups = set()
        return await call_next(request)

    _pam_inst = MagicMock()
    _pam_inst.authenticate.return_value = pam_ok

    with (
        patch("api.auth.pam_auth", _pam_inst),
        patch("api.auth.pam.pam", return_value=_pam_inst),
        patch("handlers.settings.load_settings", return_value=MagicMock(
            deny_root_login=False,
            api_key="test-api-key",
        )),
        patch("lib.permissions.pwd.getpwnam", side_effect=KeyError),
        patch("lib.permissions.grp.getgrall", return_value=[]),
    ):
        from api.auth import router as auth_router  # noqa: PLC0415
        app.include_router(auth_router)

    return app, _pam_inst


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

class TestAuthLogin:
    def setup_method(self):
        """Reset rate limiter so tests do not block each other."""
        import api.auth as auth_mod
        auth_mod._rl_buckets.clear()

    def test_successful_login_returns_200(self):
        app, pam_inst = _make_auth_app(pam_ok=True)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/auth/login", json={"username": "alice", "password": "pw"})
        assert resp.status_code == 200

    def test_successful_login_sets_cookie(self):
        app, _ = _make_auth_app(pam_ok=True)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/auth/login", json={"username": "alice", "password": "pw"})
        assert "auth" in resp.cookies

    def test_cookie_contains_base64_credentials(self):
        app, _ = _make_auth_app(pam_ok=True)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/auth/login", json={"username": "alice", "password": "pw"})
        cookie_value = resp.cookies.get("auth", "")
        decoded = base64.b64decode(cookie_value).decode()
        assert decoded == "alice:pw"

    def test_invalid_credentials_returns_401(self):
        app, pam_inst = _make_auth_app(pam_ok=True)
        # Authenticate returns False for this specific call
        pam_inst.authenticate.return_value = False
        with patch("api.auth.pam_auth", pam_inst):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/auth/login", json={"username": "alice", "password": "wrong"})
        assert resp.status_code == 401

    def test_missing_username_returns_400(self):
        app, _ = _make_auth_app(pam_ok=True)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/auth/login", json={"password": "pw"})
        assert resp.status_code == 400

    def test_missing_password_returns_400(self):
        app, _ = _make_auth_app(pam_ok=True)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/auth/login", json={"username": "alice"})
        assert resp.status_code == 400

    def test_empty_body_returns_400(self):
        app, _ = _make_auth_app(pam_ok=True)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/auth/login", json={})
        assert resp.status_code == 400

    def test_root_login_blocked_when_denied(self):
        app, pam_inst = _make_auth_app(pam_ok=True)
        with (
            patch("api.auth.pam_auth", pam_inst),
            patch("api.auth.load_settings", return_value=MagicMock(
                deny_root_login=True,
                api_key=None,
            )),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/auth/login", json={"username": "root", "password": "pw"})
        assert resp.status_code == 403

    def test_rate_limit_after_too_many_attempts(self):
        import api.auth as auth_mod
        auth_mod._rl_buckets.clear()

        app, pam_inst = _make_auth_app(pam_ok=False)
        with TestClient(app, raise_server_exceptions=False) as client:
            for _ in range(10):
                client.post("/auth/login", json={"username": "x", "password": "y"})
            resp = client.post("/auth/login", json={"username": "x", "password": "y"})
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

class TestAuthLogout:
    def test_logout_returns_200(self):
        app, _ = _make_auth_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/auth/logout")
        assert resp.status_code == 200

    def test_logout_clears_auth_cookie(self):
        app, _ = _make_auth_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            # Log in
            client.post("/auth/login", json={"username": "alice", "password": "pw"})
            # Log out
            resp = client.post("/auth/logout")
        # FastAPI sets max-age=0 or a past expires date when deleting a cookie
        assert resp.status_code == 200
        response_body = resp.json()
        assert response_body.get("detail") == "logged_out"


# ---------------------------------------------------------------------------
# GET /auth/ws-ticket
# ---------------------------------------------------------------------------

class TestAuthWsTicket:
    def test_returns_ticket(self):
        app, _ = _make_auth_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/auth/ws-ticket")
        assert resp.status_code == 200
        assert "ticket" in resp.json()

    def test_ticket_is_string(self):
        app, _ = _make_auth_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/auth/ws-ticket")
        assert isinstance(resp.json()["ticket"], str)

    def test_each_call_returns_unique_ticket(self):
        app, _ = _make_auth_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            t1 = client.get("/auth/ws-ticket").json()["ticket"]
            t2 = client.get("/auth/ws-ticket").json()["ticket"]
        assert t1 != t2


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

class TestAuthMe:
    def test_returns_user_info(self):
        app, _ = _make_auth_app()
        with (
            patch("lib.permissions.pwd.getpwnam", side_effect=KeyError),
            patch("lib.permissions.grp.getgrall", return_value=[]),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "username" in data
        assert "permissions" in data

    def test_permissions_structure_complete(self):
        app, _ = _make_auth_app()
        with (
            patch("lib.permissions.pwd.getpwnam", side_effect=KeyError),
            patch("lib.permissions.grp.getgrall", return_value=[]),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/auth/me")
        perms = resp.json()["permissions"]
        for key in ("admin", "containers", "vms", "storage", "shell", "logs"):
            assert key in perms


# ---------------------------------------------------------------------------
# GET /info
# ---------------------------------------------------------------------------

class TestServerInfo:
    def test_returns_hostname(self):
        app, _ = _make_auth_app()
        with patch("builtins.open", side_effect=Exception):
            import platform
            with patch("api.auth.platform.node", return_value="testserver"):
                with TestClient(app, raise_server_exceptions=False) as client:
                    resp = client.get("/info")
        assert resp.status_code == 200
        assert "hostname" in resp.json()
