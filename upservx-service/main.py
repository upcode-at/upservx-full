"""
UpservX - Server Management API

A comprehensive server management API built with FastAPI providing
container management, system monitoring, and server administration.
"""

import logging
import os
import socket
import ssl
import subprocess
import sys
import time

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from lib.system_utils import get_server_addresses
from lib.vnc_proxy import ensure_proxy_running
from lib.ws_tickets import create_ticket as _create_ws_ticket, consume_ticket as _consume_ws_ticket  # noqa: F401 – re-exported for routers
from lib.permissions import (
    check_api_token_permission,
    check_path_permission,
    get_user_groups,
    is_public_request,
)
from lib.cluster_security import (
    CLUSTER_TLS_PORT,
    ClusterSecurityError,
    ensure_node_tls,
    has_cluster_signature,
    verify_cluster_signature,
)
from lib.session_tokens import verify_session_token
from lib.api_tokens import migrate_legacy_api_key, verify_api_token
from lib.jobs import JOB_DB_PATH, initialize_job_store
from lib.process_model import (
    acquire_web_process_lock,
    release_web_process_lock,
    web_process_lock_held,
)
from lib.secure_store import (
    CONFIG_ROOT,
    apply_secure_umask,
    enforce_config_permissions,
)
from handlers.settings import load_settings
from lib.logger import log_system

apply_secure_umask()
PASSIVE_PROCESS = os.getenv("UPSERVX_PASSIVE_PROCESS") == "1"

# ---------------------------------------------------------------------------
# Logging – tee stdout/stderr to log file
# ---------------------------------------------------------------------------

LOG_FILE = os.getenv("UPSERVX_LOG_FILE", "/etc/upservx.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

_orig_stdout = sys.stdout
_orig_stderr = sys.stderr


class _TeeWriter:
    """Writes to both terminal and log file, so print() output is captured."""

    def __init__(self, original, log_path: str):
        self._original = original
        self._log = open(log_path, "a", buffering=1)

    def write(self, msg: str):
        self._original.write(msg)
        if msg.strip():
            self._log.write(msg if msg.endswith("\n") else msg + "\n")

    def flush(self):
        self._original.flush()
        self._log.flush()

    def fileno(self):
        return self._original.fileno()

    def isatty(self):
        return self._original.isatty()


sys.stdout = _TeeWriter(_orig_stdout, LOG_FILE)
sys.stderr = _TeeWriter(_orig_stderr, LOG_FILE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(_orig_stdout),
    ],
)
logger = logging.getLogger(__name__)


def _wait_for_cluster_listener(process: subprocess.Popen, timeout: float = 10.0) -> None:
    """Fail startup if the mandatory HTTPS cluster listener cannot bind."""

    deadline = time.monotonic() + timeout
    ready_since = None
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    tls_context.check_hostname = False
    tls_context.verify_mode = ssl.CERT_NONE
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"Cluster HTTPS listener exited during startup ({return_code})"
            )
        try:
            with socket.create_connection(
                ("127.0.0.1", CLUSTER_TLS_PORT),
                timeout=0.2,
            ) as connection:
                with tls_context.wrap_socket(connection, server_hostname="localhost"):
                    ready_since = ready_since or time.monotonic()
                    if time.monotonic() - ready_since >= 1.0:
                        return
        except (OSError, ssl.SSLError):
            ready_since = None
        time.sleep(0.1)
    raise RuntimeError("Timed out waiting for the cluster HTTPS listener")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="UpservX API",
    description="Server Management API",
    version="0.6.0",
)


@app.get("/health/live", include_in_schema=False)
def health_live() -> dict[str, str]:
    """Process liveness endpoint for local service supervision."""

    return {"status": "alive"}


@app.get("/health/ready", include_in_schema=False)
def health_ready() -> dict[str, str]:
    """Readiness requires initialized persistent state and the singleton lock."""

    if PASSIVE_PROCESS or not web_process_lock_held() or not JOB_DB_PATH.is_file():
        return Response(status_code=503)  # type: ignore[return-value]
    return {"status": "ready"}


@app.on_event("startup")
def initialize_security_stores() -> None:
    """Migrate legacy secrets and enforce the centralized file-mode policy."""

    if PASSIVE_PROCESS:
        return
    acquire_web_process_lock()
    try:
        ensure_proxy_running()
        enforce_config_permissions(CONFIG_ROOT)
        migrate_legacy_api_key(CONFIG_ROOT / "settings.json")
        from lib.totp import migrate_login_token_store

        migrate_login_token_store()
        initialize_job_store()
        enforce_config_permissions(CONFIG_ROOT)
    except Exception:
        release_web_process_lock()
        raise


@app.on_event("shutdown")
def release_process_lock() -> None:
    if not PASSIVE_PROCESS:
        release_web_process_lock()

log_system("UpservX API starting up")

# Configure CORS. For development/production, set FRONTEND_ORIGINS env to a
# comma-separated list (e.g. "http://localhost:9200,http://127.0.0.1:9200").
# If not set, auto-detect server addresses and additionally allow generic IP/
# localhost origins with any port to support direct IP access reliably.
frontend_origins = os.getenv("FRONTEND_ORIGINS")
if frontend_origins:
    allow_origins = [o.strip() for o in frontend_origins.split(",") if o.strip()]
    allow_origin_regex = None
else:
    allow_origins = get_server_addresses()
    # Allow direct browser access via IPv4/localhost with arbitrary ports.
    allow_origin_regex = r"^https?://((\d{1,3}\.){3}\d{1,3}|localhost|127\.0\.0\.1)(:\d+)?$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# PAM authentication middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def pam_auth_middleware(request: Request, call_next):
    """Authenticate signed sessions, scoped API tokens, or cluster peers."""
    server = request.scope.get("server") or (None, None)
    if server[1] == CLUSTER_TLS_PORT and not has_cluster_signature(request.headers):
        # The second app process exists only as an authenticated transport
        # listener. Browser sessions and public/API-token traffic stay on the
        # single web process so they cannot observe a second set of globals.
        return Response(status_code=401)

    if request.method == "OPTIONS":
        return await call_next(request)

    # WebSocket upgrades: let the handler authenticate itself — returning a
    # plain HTTP 401 from middleware kills the connection before the handler runs.
    if request.headers.get("upgrade", "").lower() == "websocket":
        return await call_next(request)

    # Public routes are explicit method/path pairs in the authorization policy.
    if is_public_request(request.method, request.url.path):
        return await call_next(request)

    if has_cluster_signature(request.headers):
        if (
            request.scope.get("scheme") != "https"
            or server[1] != CLUSTER_TLS_PORT
        ):
            return Response(status_code=400)
        raw_path = request.scope.get("raw_path", request.url.path.encode("ascii"))
        raw_target = raw_path.decode("ascii")
        query_string = request.scope.get("query_string", b"")
        if query_string:
            raw_target = f"{raw_target}?{query_string.decode('ascii')}"
        try:
            verified_cluster_request = verify_cluster_signature(
                request.method,
                raw_target,
                await request.body(),
                request.headers,
            )
        except ClusterSecurityError as error:
            return Response(status_code=error.status_code)
        request.state.user = "cluster-node"
        request.state.cluster_node = verified_cluster_request.node_id
        request.state.cluster_key_id = verified_cluster_request.key_id
        auth_header = None
    else:
        auth_header = request.headers.get("Authorization")

    # If Authorization header is missing, allow cookie named 'auth' to carry Bearer token.
    if not auth_header and not hasattr(request.state, "user"):
        cookie_auth = request.cookies.get("auth")
        if cookie_auth:
            if cookie_auth.lower().startswith("bearer "):
                auth_header = cookie_auth
            else:
                auth_header = f"Bearer {cookie_auth}"

    if not auth_header and not hasattr(request.state, "user"):
        return Response(status_code=401)

    if not hasattr(request.state, "user"):
        try:
            scheme, credentials = auth_header.split(" ", 1)
            scheme = scheme.lower()

            if scheme == "bearer":
                token = credentials.strip()
                api_token = verify_api_token(token)
                if api_token:
                    request.state.user = api_token.username
                    request.state.api_token = api_token
                else:
                    username = verify_session_token(token)
                    if not username:
                        return Response(status_code=401)
                    settings = load_settings()
                    if settings.deny_root_login and username == "root":
                        return Response(status_code=403)
                    request.state.user = username
            else:
                raise ValueError
        except Exception:
            return Response(status_code=401)

    # Group-based permission check
    _username = request.state.user
    _groups = get_user_groups(_username)
    request.state.groups = _groups
    if hasattr(request.state, "api_token"):
        allowed = check_api_token_permission(
            request.state.api_token,
            request.url.path,
            request.method,
        )
    else:
        allowed = check_path_permission(
            _username,
            _groups,
            request.url.path,
            request.method,
        )
    if not allowed:
        return Response(status_code=403)

    response = await call_next(request)
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

from api.auth import router as auth_router
from api.system import router as system_router
from api.containers import router as containers_router
from api.images import router as images_router
from api.firewall import router as firewall_router
from api.cluster import router as cluster_router
from api.customization import router as customization_router
from api.isos import router as isos_router
from api.vms import router as vms_router
from api.vm_networks import router as vm_networks_router
from api.network import router as network_router
from api.storage import router as storage_router
from api.users import router as users_router
from api.services import router as services_router
from api.logs import router as logs_router
from api.settings import router as settings_router
from api.backup import router as backup_router
from api.proxy import router as proxy_router
from api.security import router as security_router
from api.ha import router as ha_router
from api.jobs import router as jobs_router

app.include_router(auth_router)
app.include_router(system_router)
app.include_router(containers_router)
app.include_router(images_router)
app.include_router(firewall_router)
app.include_router(cluster_router)
app.include_router(customization_router)
app.include_router(isos_router)
app.include_router(vms_router)
app.include_router(vm_networks_router)
app.include_router(network_router)
app.include_router(storage_router)
app.include_router(users_router)
app.include_router(services_router)
app.include_router(logs_router)
app.include_router(settings_router)
app.include_router(backup_router)
app.include_router(proxy_router)
app.include_router(security_router)
app.include_router(ha_router)
app.include_router(jobs_router)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # The browser/API listener remains on 9500. Inter-node requests use a
    # separate TLS listener so cluster transport can never silently downgrade.
    ensure_node_tls()
    cluster_server_path = os.path.join(os.path.dirname(__file__), "cluster_server.py")
    cluster_server = subprocess.Popen([sys.executable, cluster_server_path])
    try:
        _wait_for_cluster_listener(cluster_server)
        # Shared runtime state is deliberately confined to one API process.
        # Long-running work runs in the separate persistent job worker.
        uvicorn.run(
            app,
            host=os.getenv("UPSERVX_API_HOST", "0.0.0.0"),
            port=9500,
            workers=1,
        )
    finally:
        cluster_server.terminate()
        try:
            cluster_server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cluster_server.kill()
            cluster_server.wait(timeout=5)
