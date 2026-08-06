"""
Integration tests for api/users.py
======================================
Tests user and group management endpoints.
System calls (pwd, grp, subprocess) are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper objects
# ---------------------------------------------------------------------------

def _make_user_app():
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = "admin"
        request.state.groups = {"sudo"}
        return await call_next(request)

    from api.users import router as users_router  # noqa: PLC0415
    app.include_router(users_router)
    return app


def _make_mock_user(username="alice", uid=1001, gid=1001, shell="/bin/bash"):
    from lib.models import SystemUserModel
    return SystemUserModel(
        username=username, uid=uid, gid=gid,
        groups=["users"], shell=shell, home=f"/home/{username}",
    )


def _make_mock_group(name="devs", gid=2001, members=None):
    from lib.models import SystemGroupModel
    return SystemGroupModel(name=name, gid=gid, members=members or [])


# ---------------------------------------------------------------------------
# GET /users
# ---------------------------------------------------------------------------

class TestListUsers:
    def test_returns_200(self):
        app = _make_user_app()
        with patch("api.users.list_system_users", return_value=[]):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/users")
        assert resp.status_code == 200

    def test_returns_users_key(self):
        app = _make_user_app()
        with patch("api.users.list_system_users", return_value=[]):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/users")
        assert "users" in resp.json()

    def test_lists_users(self):
        app = _make_user_app()
        mock_user = _make_mock_user("alice")
        with patch("api.users.list_system_users", return_value=[mock_user]):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/users")
        users = resp.json()["users"]
        assert len(users) == 1
        assert users[0]["username"] == "alice"


# ---------------------------------------------------------------------------
# POST /users
# ---------------------------------------------------------------------------

class TestCreateUser:
    _payload = {
        "username": "newuser",
        "password": "Passw0rd!",
        "groups": ["users"],
        "shell": "/bin/bash",
    }

    def test_successful_create_returns_200(self):
        app = _make_user_app()
        # api.users already imported → patch api.users.create_user binding
        with patch("api.users.create_user"):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/users", json=self._payload)
        assert resp.status_code == 200
        assert resp.json()["username"] == "newuser"

    def test_returns_created_status(self):
        app = _make_user_app()
        with patch("api.users.create_user"):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/users", json=self._payload)
        assert resp.json()["detail"] == "created"

    def test_failure_returns_400(self):
        app = _make_user_app()
        with patch("api.users.create_user", side_effect=Exception("useradd failed")):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/users", json=self._payload)
        assert resp.status_code == 400

    def test_error_message_propagated(self):
        app = _make_user_app()
        with patch("api.users.create_user", side_effect=Exception("user already exists")):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/users", json=self._payload)
        assert "user already exists" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# PUT /users/{username}
# ---------------------------------------------------------------------------

class TestUpdateUser:
    def test_update_returns_200(self):
        app = _make_user_app()
        with patch("api.users.update_user"):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.put("/users/alice", json={"shell": "/bin/zsh"})
        assert resp.status_code == 200

    def test_update_failure_returns_400(self):
        app = _make_user_app()
        with patch("api.users.update_user", side_effect=Exception("user not found")):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.put("/users/ghost", json={"shell": "/bin/bash"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /users/{username}
# ---------------------------------------------------------------------------

class TestDeleteUser:
    def test_delete_returns_200(self):
        app = _make_user_app()
        with patch("api.users.delete_user"):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.delete("/users/alice")
        assert resp.status_code == 200

    def test_delete_returns_deleted_detail(self):
        app = _make_user_app()
        with patch("api.users.delete_user"):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.delete("/users/alice")
        assert resp.json()["detail"] == "deleted"

    def test_delete_nonexistent_user_returns_400(self):
        app = _make_user_app()
        with patch("api.users.delete_user", side_effect=Exception("user not found")):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.delete("/users/ghost")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /users/{username}/keys
# ---------------------------------------------------------------------------

class TestSSHKeys:
    def test_get_keys_returns_200(self):
        app = _make_user_app()
        with patch("api.users.read_authorized_keys", return_value=[]):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/users/alice/keys")
        assert resp.status_code == 200
        assert "keys" in resp.json()

    def test_get_keys_returns_actual_keys(self):
        pub_key = "ssh-rsa AAAA...== alice@host"
        app = _make_user_app()
        with patch("api.users.read_authorized_keys", return_value=[pub_key]):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/users/alice/keys")
        assert resp.json()["keys"] == [pub_key]

    def test_put_keys_returns_200(self):
        app = _make_user_app()
        with patch("api.users.write_authorized_keys"):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.put("/users/alice/keys", json={"keys": ["ssh-rsa AAAA..."]})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /groups & POST /groups
# ---------------------------------------------------------------------------

class TestGroups:
    def test_list_groups_returns_200(self):
        app = _make_user_app()
        with patch("api.users.list_system_groups", return_value=[]):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/groups")
        assert resp.status_code == 200

    def test_create_group_success(self):
        app = _make_user_app()
        with patch("api.users.create_group"):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/groups", json={"name": "devs", "members": []})
        assert resp.status_code == 200

    def test_create_group_failure_returns_400(self):
        app = _make_user_app()
        with patch("api.users.create_group", side_effect=Exception("group exists")):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post("/groups", json={"name": "devs", "members": []})
        assert resp.status_code == 400
