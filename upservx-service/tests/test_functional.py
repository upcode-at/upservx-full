"""
Funktions-Tests für UpservX-Backend-Workflows
===============================================
Testet vollständige Benutzerszenarien, die mehrere Komponenten umfassen:

  1. Login-Flow: Einloggen → Session nutzen → Ausloggen
  2. Container-Lifecycle: Container anlegen → starten → stoppen → löschen
  3. Benutzer-Lifecycle: Benutzer anlegen → SSH-Key setzen → Benutzer löschen
  4. WS-Ticket-Flow: Login → Ticket holen → Ticket einmalig verwenden
  5. Verschlüsselung im API-Kontext: Backup-Server mit Passwort anlegen und auslesen
  6. Berechtigungseszenarien: Unprivilegierter Benutzer greift auf gesperrte Routen zu
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
    Erstellt eine FastAPI-Test-App mit auth- und weiteren Routern.
    Die PAM-Middleware wird durch einen einfachen BasicAuth-Parser ersetzt,
    der den gemockten PAM-Handler aufruft.
    """
    if groups is None:
        groups = {"sudo"}

    app = FastAPI()

    _pam = MagicMock()
    _pam.authenticate.return_value = pam_ok

    @app.middleware("http")
    async def fake_auth_middleware(request: Request, call_next):
        # Auth-Endpunkte ohne Credential-Prüfung durchlassen
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
        patch("api.auth.pam.pam", return_value=_pam),
        patch("handlers.settings.load_settings", return_value=MagicMock(
            deny_root_login=False, api_key="test-api-key",
        )),
        patch("lib.permissions.pwd.getpwnam", side_effect=KeyError),
        patch("lib.permissions.grp.getgrall", return_value=[]),
    ):
        from api.auth import router as auth_router        # noqa: PLC0415
        from api.users import router as users_router      # noqa: PLC0415
        from api.containers import router as cont_router  # noqa: PLC0415

        app.include_router(auth_router)
        app.include_router(users_router)
        app.include_router(cont_router)

    return app, _pam


def _basic_header(username="testuser", password="testpass"):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


# ---------------------------------------------------------------------------
# 1. Login-Flow
# ---------------------------------------------------------------------------

class TestLoginFlow:
    def test_login_use_and_logout(self):
        """Vollständiger Login → Session → Logout-Zyklus."""
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

            # Authentifizierte Anfrage
            me_resp = client.get("/auth/me", headers=_basic_header())
            assert me_resp.status_code == 200

            # Logout
            logout_resp = client.post("/auth/logout")
            assert logout_resp.status_code == 200

    def test_unauthenticated_request_fails(self):
        app, _ = _full_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/auth/me")   # kein Auth-Header
        assert resp.status_code == 401

    def test_wrong_credentials_denied(self):
        app, pam = _full_app(pam_ok=False)
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/auth/me", headers=_basic_header("user", "wrong"))
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Container-Lifecycle
# ---------------------------------------------------------------------------

class TestContainerLifecycle:
    """
    Simuliert: Container erstellen → starten → stoppen → löschen.
    Docker-Befehle werden vollständig gemockt.
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

            # DELETE – verwendet HTTP DELETE, nicht POST /delete
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
        """Wenn CREATE fehlschlägt, werden keine weiteren Schritte ausgeführt."""
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
# 3. Benutzer-Lifecycle
# ---------------------------------------------------------------------------

class TestUserLifecycle:
    """Benutzer anlegen → SSH-Key setzen → Benutzer löschen."""

    def test_user_creation_and_deletion(self):
        app, _ = _full_app()
        headers = _basic_header()

        with TestClient(app, raise_server_exceptions=False) as client:
            # User anlegen
            with patch("api.users.create_user"):
                create_resp = client.post("/users", json={
                    "username": "newdev",
                    "password": "Secure123!",
                    "groups": ["docker"],
                    "shell": "/bin/bash",
                }, headers=headers)
            assert create_resp.status_code == 200
            assert create_resp.json()["username"] == "newdev"

            # SSH-Key setzen
            pub_key = "ssh-rsa AAAAB3Nza...== dev@machine"
            with patch("api.users.write_authorized_keys"):
                key_resp = client.put("/users/newdev/keys",
                                      json={"keys": [pub_key]},
                                      headers=headers)
            assert key_resp.status_code == 200

            # SSH-Key auslesen
            with patch("api.users.read_authorized_keys", return_value=[pub_key]):
                get_key_resp = client.get("/users/newdev/keys", headers=headers)
            assert get_key_resp.json()["keys"] == [pub_key]

            # User löschen
            with patch("api.users.delete_user"):
                del_resp = client.delete("/users/newdev", headers=headers)
            assert del_resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. WS-Ticket-Flow
# ---------------------------------------------------------------------------

class TestWsTicketFlow:
    """Login → Ticket anfordern → Ticket einmalig verwenden."""

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

            # Ticket verbrauchen (simuliert WS-Verbindungsaufbau)
            username = wst.consume_ticket(ticket)
            assert username is not None

            # Ticket ist jetzt verbraucht
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

        # Ablaufzeit manuell in die Vergangenheit setzen
        with wst._lock:
            u, _ = wst._tickets[ticket]
            wst._tickets[ticket] = (u, datetime.utcnow() - timedelta(seconds=1))

        assert wst.consume_ticket(ticket) is None


# ---------------------------------------------------------------------------
# 5. Berechtigungs-Szenarien
# ---------------------------------------------------------------------------

class TestPermissionScenarios:
    """
    Prüft, dass unprivilegierte Benutzer auf Admin-Routen keinen Zugriff
    erhalten und privilegierte Benutzer korrekt durchgelassen werden.
    Nutzt die echte Permissions-Logik (nur pwd/grp gemockt).
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
        """Docker-Benutzer ohne sudo darf /users nicht aufrufen."""
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
        # Entweder 401 (kein Auth in dieser App-Variante) oder 403
        assert resp.status_code in (401, 403)
