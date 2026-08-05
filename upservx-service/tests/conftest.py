"""
Shared pytest fixtures for the UpservX backend test stack.

Structure
---------
- `app`          – FastAPI test application with mocked PAM and disabled
                   side effects (TeeWriter, VNC proxy, …).
- `client`       – synchronous httpx test client for integration/functional tests.
- `auth_headers` – Basic Auth header representing a logged-in user.
"""

import os
import sys
import types
import importlib
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lib.api_tokens import ApiTokenPrincipal

# ---------------------------------------------------------------------------
# Register stub modules that only exist on the real server
# (pam, uvicorn, etc.) – must be set BEFORE the first `import main`.
# ---------------------------------------------------------------------------

def _register_stub(name: str, **attrs):
    """Creates an empty stub module and registers it in sys.modules."""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)


# pam – PAM authentication (not available in CI)
_pam_instance = MagicMock()
_pam_instance.authenticate.return_value = True
_pam_class = MagicMock(return_value=_pam_instance)
_register_stub("pam", pam=_pam_class)

# uvicorn – only used in main.py under __main__
_register_stub("uvicorn")


# ---------------------------------------------------------------------------
# Suppress side effects in main.py (TeeWriter, VNC proxy, logging files)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app(tmp_path_factory):
    """
    Returns a fully configured FastAPI test application.

    Setup happens only once per test session (scope='session') because
    main.py creates logging files and registers middleware on import.
    """
    test_log_file = tmp_path_factory.mktemp("upservx-logs") / "upservx.log"

    with (
        patch.dict(os.environ, {"UPSERVX_LOG_FILE": str(test_log_file)}),
        patch("builtins.open", wraps=open),                  # allow filesystem writes
        patch("os.makedirs"),                                  # do not create /etc/upservx
        patch("os.chmod"),                                     # do not mutate runtime key dirs
        patch("lib.vnc_proxy.ensure_proxy_running"),           # do not start VNC process
        patch("handlers.settings.load_settings", return_value=MagicMock(
            deny_root_login=False,
        )),
        patch("pam.pam", return_value=_pam_instance),
    ):
        # main einmal importieren (oder aus dem Cache holen)
        if "main" in sys.modules:
            _app = sys.modules["main"].app
        else:
            import main as _main_mod  # noqa: PLC0415
            _app = _main_mod.app
    _main_module = sys.modules["main"]
    _main_module.verify_api_token = lambda token: (
        ApiTokenPrincipal(
            token_id="test",
            name="Test administrator token",
            role="admin",
            scopes=frozenset({"*"}),
            expires_at=None,
        )
        if token == "test-api-key"
        else None
    )
    yield _app


@pytest.fixture()
def client(app):
    """Synchronous TestClient for integration and functional tests."""
    import main as main_module  # noqa: PLC0415
    import lib.totp as totp_module  # noqa: PLC0415

    # Startup migration is covered against isolated stores by unit tests. Each
    # client gets narrowly scoped patches so later security tests still execute
    # the real migration functions.
    with (
        patch.object(main_module, "enforce_config_permissions", return_value={}),
        patch.object(main_module, "migrate_legacy_api_key", return_value=False),
        patch.object(main_module, "initialize_job_store"),
        patch.object(main_module, "acquire_web_process_lock"),
        patch.object(main_module, "release_web_process_lock"),
        patch.object(totp_module, "migrate_login_token_store"),
        TestClient(app, raise_server_exceptions=False) as c,
    ):
        yield c


@pytest.fixture()
def auth_headers():
    """
    Basic Auth header for a fictional user `testuser`.

    In integration tests, PAM is mocked so that any password is accepted.
    The header uses the format expected by the middleware.
    """
    import base64
    token = base64.b64encode(b"testuser:testpassword").decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture()
def api_key_headers():
    """Bearer header for a mocked hashed administrator API token."""
    return {"Authorization": "Bearer test-api-key"}
