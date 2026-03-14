"""
Shared pytest fixtures für den UpservX-Backend-Teststack.

Struktur
--------
- `app`          – FastAPI-Testapplikation mit gemocktem PAM und deaktivierten
                   Seiteneffekten (TeeWriter, VNC-Proxy, …).
- `client`       – synchroner httpx-Testclient für Integrations-/Funktionstests.
- `auth_headers` – Basic-Auth-Header als "eingeloggter" Benutzer.
"""

import sys
import types
import importlib
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Stub-Module registrieren, die nur auf dem echten Server vorhanden sind
# (pam, uvicorn, usw.)  – müssen VOR dem ersten `import main` gesetzt werden.
# ---------------------------------------------------------------------------

def _register_stub(name: str, **attrs):
    """Erstellt ein leeres Stub-Modul und registriert es in sys.modules."""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules.setdefault(name, mod)


# pam – PAM-Authentifizierung (läuft nicht in CI)
_pam_instance = MagicMock()
_pam_instance.authenticate.return_value = True
_pam_class = MagicMock(return_value=_pam_instance)
_register_stub("pam", pam=_pam_class)

# uvicorn – wird in main.py nur unter __main__ gebraucht
_register_stub("uvicorn")


# ---------------------------------------------------------------------------
# Seiteneffekte in main.py unterdrücken (TeeWriter, VNC-Proxy, Logging-Files)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app():
    """
    Gibt eine fertig konfigurierte FastAPI-Testapp zurück.

    Der Aufbau geschieht nur einmal pro Test-Session (scope='session'), weil
    main.py beim Import Logging-Dateien anlegt und Middleware registriert.
    """
    with (
        patch("builtins.open", wraps=open),                  # FS-Schreibzugriffe erlaubt
        patch("os.makedirs"),                                  # kein /etc/upservx anlegen
        patch("lib.vnc_proxy.ensure_proxy_running"),           # kein VNC-Prozess starten
        patch("handlers.settings.load_settings", return_value=MagicMock(
            deny_root_login=False,
            api_key="test-api-key",
        )),
        patch("pam.pam", return_value=_pam_instance),
    ):
        # main einmal importieren (oder aus dem Cache holen)
        if "main" in sys.modules:
            _app = sys.modules["main"].app
        else:
            import main as _main_mod  # noqa: PLC0415
            _app = _main_mod.app
        yield _app


@pytest.fixture(scope="session")
def client(app):
    """Synchroner TestClient für Integrations- und Funktionstests."""
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def auth_headers():
    """
    Basic-Auth-Header für einen fiktiven User `testuser`.

    In den Integrationstests wird PAM gemockt, sodass jedes Passwort akzeptiert
    wird.  Der Header hat das Format, das die Middleware erwartet.
    """
    import base64
    token = base64.b64encode(b"testuser:testpassword").decode()
    return {"Authorization": f"Basic {token}"}


@pytest.fixture()
def api_key_headers():
    """Bearer-Token für API-Key-Authentifizierung (test-api-key)."""
    return {"Authorization": "Bearer test-api-key"}
