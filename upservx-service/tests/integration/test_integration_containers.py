"""
Integration tests for api/containers.py
==========================================
Tests container endpoints via the FastAPI router.
Docker/LXC processes are replaced with mocks.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Test app factory
# ---------------------------------------------------------------------------

def _make_container_app():
    """Creates an isolated test app with container router."""
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = "testuser"
        request.state.groups = {"docker"}
        return await call_next(request)

    from api.containers import router as containers_router  # noqa: PLC0415
    app.include_router(containers_router)
    return app


# ---------------------------------------------------------------------------
# GET /containers
# ---------------------------------------------------------------------------

class TestListContainers:
    def test_returns_list(self):
        from lib.models import Container
        mock_container = Container(
            id=1, name="web", type="docker", status="running",
            image="nginx:latest", cpu=0.1, memory=64, created="2025-01-01",
        )
        app = _make_container_app()
        with patch("api.containers.list_all_containers", return_value=[mock_container]):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/containers")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_empty_list_when_no_containers(self):
        app = _make_container_app()
        with patch("api.containers.list_all_containers", return_value=[]):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/containers")
        assert resp.json() == []

    def test_container_fields_present(self):
        from lib.models import Container
        mock_container = Container(
            id=1, name="db", type="docker", status="stopped",
            image="postgres:15", cpu=0.5, memory=512, created="2025-01-01",
        )
        app = _make_container_app()
        with patch("api.containers.list_all_containers", return_value=[mock_container]):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/containers")
        container_data = resp.json()[0]
        for field in ("id", "name", "type", "status", "image"):
            assert field in container_data


# ---------------------------------------------------------------------------
# POST /containers (Docker)
# ---------------------------------------------------------------------------

class TestCreateDockerContainer:
    _payload = {
        "name": "myapp",
        "type": "docker",
        "image": "nginx:latest",
        "ports": ["8080:80"],
        "mounts": [],
        "envs": [],
        "cpu": 0.5,
        "memory": 128,
    }

    def test_docker_not_installed_returns_404(self):
        app = _make_container_app()
        with patch("api.containers.shutil.which", return_value=None):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/containers", json=self._payload)
        assert resp.status_code == 404
        assert "docker not installed" in resp.json()["detail"]

    def test_successful_docker_create(self):
        from lib.models import Container
        mock_container = Container(
            id=1, name="myapp", type="docker", status="running",
            image="nginx:latest", cpu=0.5, memory=128, created="2025-01-01",
        )
        app = _make_container_app()
        with (
            patch("api.containers.shutil.which", return_value="/usr/bin/docker"),
            patch("api.containers.subprocess.run", return_value=MagicMock(
                returncode=0, stdout="abc123def", stderr=""
            )),
            patch("handlers.containers.get_docker_containers", return_value=[mock_container]),
            patch("handlers.notifications.notify"),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/containers", json=self._payload)
        assert resp.status_code == 200

    def test_docker_create_failure_returns_400(self):
        app = _make_container_app()
        with (
            patch("api.containers.shutil.which", return_value="/usr/bin/docker"),
            patch("api.containers.subprocess.run", return_value=MagicMock(
                returncode=1, stdout="", stderr="image not found"
            )),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/containers", json=self._payload)
        assert resp.status_code == 400

    def test_unknown_container_type_creates_api_container(self):
        """Unknown types are stored as API containers (no error)."""
        payload = {**self._payload, "type": "unknowntype"}
        app = _make_container_app()
        with patch("api.containers.shutil.which", return_value="/usr/bin/docker"):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/containers", json=payload)
        # The else branch in create_container creates an API container → 200
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /containers (LXC)
# ---------------------------------------------------------------------------

class TestCreateLXCContainer:
    _payload = {
        "name": "mycontainer",
        "type": "lxc",
        "image": "ubuntu:22.04",
        "ports": [],
        "mounts": [],
        "envs": [],
        "cpu": 1.0,
        "memory": 256,
    }

    def test_lxc_not_installed_returns_404(self):
        app = _make_container_app()
        with patch("api.containers.shutil.which", return_value=None):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/containers", json=self._payload)
        assert resp.status_code == 404

    def test_successful_lxc_create(self):
        from lib.models import Container
        mock_container = Container(
            id=2, name="mycontainer", type="LXC", status="running",
            image="ubuntu:22.04", cpu=1.0, memory=256, created="2025-01-01",
        )
        app = _make_container_app()

        def _which(cmd):
            return "/usr/bin/lxc" if cmd == "lxc" else None

        with (
            patch("api.containers.shutil.which", side_effect=_which),
            patch("api.containers.subprocess.run", return_value=MagicMock(returncode=0, stderr="")),
            patch("handlers.containers.get_lxc_containers", return_value=[mock_container]),
            patch("handlers.notifications.notify"),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/containers", json=self._payload)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Container-Aktionen: start / stop / delete
# ---------------------------------------------------------------------------

class TestContainerActions:
    def _post_action(self, action: str, returncode: int = 0):
        app = _make_container_app()
        with (
            patch("api.containers.subprocess.run", return_value=MagicMock(
                returncode=returncode, stdout="", stderr="error" if returncode else ""
            )),
            patch("api.containers.shutil.which", return_value="/usr/bin/docker"),
            patch("api.containers.find_container_type", return_value="docker"),
            patch("handlers.notifications.notify"),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                return client.post(f"/containers/myapp/{action}")

    def _delete_action(self, returncode: int = 0):
        app = _make_container_app()
        with (
            patch("api.containers.subprocess.run", return_value=MagicMock(
                returncode=returncode, stdout="", stderr="error" if returncode else ""
            )),
            patch("api.containers.shutil.which", return_value="/usr/bin/docker"),
            patch("api.containers.find_container_type", return_value="docker"),
            patch("handlers.notifications.notify"),
        ):
            with TestClient(app, raise_server_exceptions=False) as client:
                return client.delete("/containers/myapp")

    def test_start_container_success(self):
        resp = self._post_action("start")
        assert resp.status_code == 200

    def test_stop_container_success(self):
        resp = self._post_action("stop")
        assert resp.status_code == 200

    def test_delete_container_success(self):
        resp = self._delete_action(returncode=0)
        assert resp.status_code == 200

    def test_action_failure_returns_400(self):
        resp = self._post_action("start", returncode=1)
        assert resp.status_code == 400
