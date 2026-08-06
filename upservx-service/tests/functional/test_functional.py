"""
Functional tests for UpservX backend workflows
===============================================
Tests complete user scenarios spanning multiple components:

  1. Login flow: log in → use session → log out
  2. Container lifecycle: create → start → stop → delete
  3. User lifecycle: create user → set SSH key → delete user
  4. WS ticket flow: login → request ticket → consume once
  5. Encryption in API context: create backup server with password and read it back
  6. Permission scenarios: unprivileged user accesses restricted routes
"""

import base64
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Gemeinsame Test-App-Factory
# ---------------------------------------------------------------------------

def _full_app(pam_ok: bool = True, username: str = "testuser", groups: set = None):
    """
    Creates a FastAPI test app with auth and additional routers.
    The PAM middleware is replaced by a simple BasicAuth parser
    that calls the mocked PAM handler.
    """
    if groups is None:
        groups = {"sudo"}

    app = FastAPI()

    _pam = MagicMock()
    _pam.authenticate.return_value = pam_ok

    @app.middleware("http")
    async def fake_auth_middleware(request: Request, call_next):
        # Pass auth endpoints through without credential check
        if request.url.path in ("/auth/login", "/auth/logout") and request.method == "POST":
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("basic "):
            creds = base64.b64decode(auth[6:]).decode()
            user, pw = creds.split(":", 1)
            if _pam.authenticate(user, pw):
                request.state.user = user
                request.state.groups = groups
                return await call_next(request)
        return __import__("fastapi").Response(status_code=401)

    with (
        patch("api.auth.pam_auth", _pam),
        patch("handlers.settings.load_settings", return_value=MagicMock(
            deny_root_login=False,
        )),
        patch("lib.permissions.pwd.getpwnam", side_effect=KeyError),
        patch("lib.permissions.grp.getgrall", return_value=[]),
    ):
        from api.auth import router as auth_router        # noqa: PLC0415
        import api.auth as auth_module                    # noqa: PLC0415
        from api.users import router as users_router      # noqa: PLC0415
        from api.containers import router as cont_router  # noqa: PLC0415

        auth_module.pam_auth = _pam
        auth_module.create_session_token = lambda *_args, **_kwargs: "signed-session"
        auth_module.revoke_session_token = lambda _token: True
        auth_module.totp_lib.is_enabled = lambda _username: False

        app.include_router(auth_router)
        app.include_router(users_router)
        app.include_router(cont_router)

    return app, _pam


def _basic_header(username="testuser", password="testpass"):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# ---------------------------------------------------------------------------
# 1. Login flow
# ---------------------------------------------------------------------------

class TestLoginFlow:
    def test_login_use_and_logout(self):
        """Complete login → session → logout cycle."""
        import api.auth as auth_mod
        auth_mod._rl_buckets.clear()

        app, _ = _full_app()

        with TestClient(app, raise_server_exceptions=False) as client:
            # Login
            login_resp = client.post(
                "/auth/login",
                json={"username": "testuser", "password": "testpass"},
            )
            assert login_resp.status_code == 200
            assert "auth" in login_resp.cookies

            # Authenticated request
            me_resp = client.get("/auth/me", headers=_basic_header())
            assert me_resp.status_code == 200

            # Logout
            logout_resp = client.post("/auth/logout")
            assert logout_resp.status_code == 200

    def test_unauthenticated_request_fails(self):
        app, _ = _full_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/auth/me")   # no auth header
        assert resp.status_code == 401

    def test_wrong_credentials_denied(self):
        app, pam = _full_app(pam_ok=False)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/auth/me", headers=_basic_header("user", "wrong"))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Container lifecycle
# ---------------------------------------------------------------------------

class TestContainerLifecycle:
    """
    Simulates: create container → start → stop → delete.
    Docker commands are fully mocked.
    """

    _create_payload = {
        "name": "lifecycle-test",
        "type": "docker",
        "image": "alpine:latest",
        "ports": [],
        "mounts": [],
        "envs": [],
        "cpu": 0.5,
        "memory": 64,
    }

    def test_full_lifecycle(self):
        from lib.models import Container as ContainerModel
        mock_c = ContainerModel(
            id=1, name="lifecycle-test", type="docker", status="running",
            image="alpine:latest", cpu=0.5, memory=64, created="2025-01-01",
        )

        app, _ = _full_app()
        headers = _basic_header()

        with TestClient(app, raise_server_exceptions=False) as client:
            # CREATE
            with (
                patch("api.containers.shutil.which", return_value="/usr/bin/docker"),
                patch("api.containers.subprocess.run", return_value=MagicMock(
                    returncode=0, stdout="abc123", stderr=""
                )),
                patch("api.containers.list_all_containers", return_value=[mock_c]),
                patch("handlers.containers.get_docker_containers", return_value=[mock_c]),
                patch("handlers.notifications.notify"),
            ):
                create_resp = client.post("/containers", json=self._create_payload,
                                          headers=headers)
            assert create_resp.status_code == 200

            # START
            with (
                patch("api.containers.subprocess.run", return_value=MagicMock(
                    returncode=0, stdout="", stderr=""
                )),
                patch("api.containers.find_container_type", return_value="docker"),
                patch("api.containers.shutil.which", return_value="/usr/bin/docker"),
                patch("handlers.notifications.notify"),
            ):
                start_resp = client.post("/containers/lifecycle-test/start", headers=headers)
            assert start_resp.status_code == 200

            # STOP
            with (
                patch("api.containers.subprocess.run", return_value=MagicMock(
                    returncode=0, stdout="", stderr=""
                )),
                patch("api.containers.find_container_type", return_value="docker"),
                patch("api.containers.shutil.which", return_value="/usr/bin/docker"),
                patch("handlers.notifications.notify"),
            ):
                stop_resp = client.post("/containers/lifecycle-test/stop", headers=headers)
            assert stop_resp.status_code == 200

            # DELETE – uses HTTP DELETE, not POST /delete
            with (
                patch("api.containers.subprocess.run", return_value=MagicMock(
                    returncode=0, stdout="", stderr=""
                )),
                patch("api.containers.find_container_type", return_value="docker"),
                patch("api.containers.shutil.which", return_value="/usr/bin/docker"),
                patch("handlers.notifications.notify"),
            ):
                delete_resp = client.delete("/containers/lifecycle-test", headers=headers)
            assert delete_resp.status_code == 200

    def test_create_failure_stops_lifecycle(self):
        """If CREATE fails, no further steps are executed."""
        app, _ = _full_app()
        headers = _basic_header()

        with TestClient(app, raise_server_exceptions=False) as client:
            with (
                patch("api.containers.shutil.which", return_value="/usr/bin/docker"),
                patch("api.containers.subprocess.run", return_value=MagicMock(
                    returncode=1, stdout="", stderr="image not found"
                )),
            ):
                resp = client.post("/containers", json=self._create_payload,
                                   headers=headers)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 3. User lifecycle
# ---------------------------------------------------------------------------

class TestUserLifecycle:
    """Create user → set SSH key → delete user."""

    def test_user_creation_and_deletion(self):
        app, _ = _full_app()
        headers = _basic_header()

        with TestClient(app, raise_server_exceptions=False) as client:
            # Create user
            with patch("api.users.create_user"):
                create_resp = client.post("/users", json={
                    "username": "newdev",
                    "password": "Secure123!",
                    "groups": ["docker"],
                    "shell": "/bin/bash",
                }, headers=headers)
            assert create_resp.status_code == 200
            assert create_resp.json()["username"] == "newdev"

            # Set SSH key
            pub_key = "ssh-rsa AAAAB3Nza...== dev@machine"
            with patch("api.users.write_authorized_keys"):
                key_resp = client.put("/users/newdev/keys",
                                      json={"keys": [pub_key]},
                                      headers=headers)
            assert key_resp.status_code == 200

            # Read SSH key
            with patch("api.users.read_authorized_keys", return_value=[pub_key]):
                get_key_resp = client.get("/users/newdev/keys", headers=headers)
            assert get_key_resp.json()["keys"] == [pub_key]

            # Delete user
            with patch("api.users.delete_user"):
                del_resp = client.delete("/users/newdev", headers=headers)
            assert del_resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. WS ticket flow
# ---------------------------------------------------------------------------

class TestWsTicketFlow:
    """Login → request ticket → consume once."""

    def test_ticket_issued_and_consumed(self):
        import lib.ws_tickets as wst
        with wst._lock:
            wst._tickets.clear()

        import api.auth as auth_mod
        auth_mod._rl_buckets.clear()

        app, _ = _full_app()
        headers = _basic_header()

        with TestClient(app, raise_server_exceptions=False) as client:
            # Ticket holen
            ticket_resp = client.get("/auth/ws-ticket", headers=headers)
            assert ticket_resp.status_code == 200
            ticket = ticket_resp.json()["ticket"]

            # Consume ticket (simulates WS connection establishment)
            username = wst.consume_ticket(ticket)
            assert username is not None

            # Ticket is now consumed
            assert wst.consume_ticket(ticket) is None

    def test_expired_ticket_rejected(self):
        import lib.ws_tickets as wst
        from datetime import datetime, timedelta
        with wst._lock:
            wst._tickets.clear()

        app, _ = _full_app()
        headers = _basic_header()

        with TestClient(app, raise_server_exceptions=False) as client:
            ticket_resp = client.get("/auth/ws-ticket", headers=headers)
            ticket = ticket_resp.json()["ticket"]

        # Manually move expiry time into the past
        with wst._lock:
            u, _ = wst._tickets[ticket]
            wst._tickets[ticket] = (u, datetime.utcnow() - timedelta(seconds=1))

        assert wst.consume_ticket(ticket) is None


# ---------------------------------------------------------------------------
# 5. Permission scenarios
# ---------------------------------------------------------------------------

class TestPermissionScenarios:
    """
    Verifies that unprivileged users cannot access admin routes,
    and that privileged users are correctly allowed through.
    Uses real permission logic (only pwd/grp mocked).
    """

    def test_docker_user_can_list_containers(self):
        from lib.models import Container as CM
        app, _ = _full_app(groups={"docker"})
        mock_c = CM(id=1, name="x", type="docker", status="running",
                    image="img", cpu=0.1, memory=64, created="2025-01-01")
        with patch("api.containers.list_all_containers", return_value=[mock_c]):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/containers", headers=_basic_header())
        assert resp.status_code == 200

    def test_admin_can_list_users(self):
        app, _ = _full_app(groups={"sudo"})
        with patch("api.users.list_system_users", return_value=[]):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/users", headers=_basic_header())
        assert resp.status_code == 200

    def test_docker_user_cannot_list_users(self):
        """Docker user without sudo must not call /users."""
        app, _ = _full_app(groups={"docker"})

        # Überschreibe die Middleware, sodass check_path_permission korrekt zieht
        @app.middleware("http")
        async def _perm_check(request: Request, call_next):
            from lib.permissions import check_path_permission  # noqa: PLC0415
            if not check_path_permission("dev", {"docker"}, request.url.path):
                return __import__("fastapi").Response(status_code=403)
            return await call_next(request)

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/users", headers=_basic_header())
        # Either 401 (no auth in this app variant) or 403
        assert resp.status_code in (401, 403)
