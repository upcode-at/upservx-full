"""
UpservX - Server Management API

A comprehensive server management API built with FastAPI providing
container management, system monitoring, and server administration.
"""

import base64
import logging
import os
import sys
import threading
from collections import defaultdict
from datetime import datetime, timedelta

import pam
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from lib.system_utils import get_server_addresses
from lib.vnc_proxy import ensure_proxy_running
from lib.ws_tickets import create_ticket as _create_ws_ticket, consume_ticket as _consume_ws_ticket  # noqa: F401 – re-exported for routers
from lib.permissions import get_user_groups, check_path_permission
from handlers.settings import load_settings
from lib.logger import log_system

# ---------------------------------------------------------------------------
# Logging – tee stdout/stderr to log file
# ---------------------------------------------------------------------------

LOG_FILE = "/etc/upservx.log"
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

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="UpservX API",
    description="Server Management API",
    version="1.0.0",
)

log_system("UpservX API starting up")

# Configure CORS. For development, set FRONTEND_ORIGINS env to a comma-separated
# list (e.g. "http://localhost:9200,http://127.0.0.1:9200"). If not set, automatically
# detect all server IP addresses, hostnames, and common dev origins.
frontend_origins = os.getenv("FRONTEND_ORIGINS")
if frontend_origins:
    allow_origins = [o.strip() for o in frontend_origins.split(",") if o.strip()]
else:
    allow_origins = get_server_addresses()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_proxy_running()

pam_auth = pam.pam()

# ---------------------------------------------------------------------------
# Generic in-memory rate limiter
# ---------------------------------------------------------------------------
_rl_buckets: dict = defaultdict(list)   # key -> [datetime, ...]
_rl_lock = threading.Lock()


def _check_rate_limit(key: str, max_attempts: int, window_seconds: int) -> bool:
    """Return True if the key is within its allowed rate, False if exceeded."""
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_seconds)
    with _rl_lock:
        attempts = [t for t in _rl_buckets[key] if t > cutoff]
        _rl_buckets[key] = attempts
        if len(attempts) >= max_attempts:
            return False
        _rl_buckets[key].append(now)
        return True


# ---------------------------------------------------------------------------
# PAM authentication middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def pam_auth_middleware(request: Request, call_next):
    """Authentication middleware using PAM or API key."""
    if request.method == "OPTIONS":
        return await call_next(request)

    # WebSocket upgrades: let the handler authenticate itself — returning a
    # plain HTTP 401 from middleware kills the connection before the handler runs.
    if request.headers.get("upgrade", "").lower() == "websocket":
        return await call_next(request)

    # Skip authentication for app store icons (public assets)
    if "/app-store/apps/" in request.url.path and request.url.path.endswith("/icon"):
        return await call_next(request)

    # Skip authentication for ISO file downloads (read-only, large files used for VM installation)
    if request.url.path.startswith("/isos/") and request.url.path.endswith("/file") and request.method == "GET":
        return await call_next(request)

    # Skip authentication for customization read endpoints (public – used on login screen)
    if request.url.path.startswith("/settings/customization") and request.method == "GET":
        return await call_next(request)

    if request.url.path == "/auth/login" and request.method == "POST":
        return await call_next(request)

    # Skip authentication for 2FA completion (uses its own temp-token auth)
    if request.url.path == "/auth/2fa/complete" and request.method == "POST":
        return await call_next(request)

    # Skip authentication for /cluster/register (validates cluster key internally)
    if request.url.path == "/cluster/register" and request.method == "POST":
        return await call_next(request)

    # Skip middleware auth for cluster replication endpoints - they handle auth internally
    if (
        request.url.path.startswith("/cluster/export")
        or request.url.path.startswith("/cluster/download")
        or request.url.path.startswith("/cluster/upload")
        or request.url.path.startswith("/cluster/import")
    ):
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    # If Authorization header is missing, allow cookie named 'auth' to carry the Basic token
    if not auth_header:
        cookie_auth = request.cookies.get("auth")
        if cookie_auth:
            if cookie_auth.lower().startswith("basic "):
                auth_header = cookie_auth
            else:
                auth_header = f"Basic {cookie_auth}"

    if not auth_header:
        return Response(status_code=401)

    try:
        scheme, credentials = auth_header.split(" ", 1)
        scheme = scheme.lower()

        if scheme == "basic":
            decoded = base64.b64decode(credentials).decode()
            username, password = decoded.split(":", 1)
            _settings = load_settings()
            if _settings.deny_root_login and username == "root":
                return Response(status_code=403)
            if not pam_auth.authenticate(username, password):
                return Response(status_code=401)
            request.state.user = username
        elif scheme == "bearer":
            settings = load_settings()
            token = credentials.strip()

            if settings.api_key and token == settings.api_key:
                request.state.user = "api-key"
            else:
                from api.cluster import get_cluster_key, read_master_config

                cluster_key = get_cluster_key()
                if cluster_key and token == cluster_key:
                    request.state.user = "cluster-node"
                else:
                    master_config = read_master_config()
                    if master_config and master_config.get("key") == token:
                        request.state.user = "cluster-master"
                    else:
                        return Response(status_code=401)
        else:
            raise ValueError
    except Exception:
        return Response(status_code=401)

    # Group-based permission check
    _username = request.state.user
    _groups = get_user_groups(_username)
    request.state.groups = _groups
    if not check_path_permission(_username, _groups, request.url.path):
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
from api.network import router as network_router
from api.storage import router as storage_router
from api.users import router as users_router
from api.services import router as services_router
from api.logs import router as logs_router
from api.settings import router as settings_router
from api.backup import router as backup_router
from api.proxy import router as proxy_router

app.include_router(auth_router)
app.include_router(system_router)
app.include_router(containers_router)
app.include_router(images_router)
app.include_router(firewall_router)
app.include_router(cluster_router)
app.include_router(customization_router)
app.include_router(isos_router)
app.include_router(vms_router)
app.include_router(network_router)
app.include_router(storage_router)
app.include_router(users_router)
app.include_router(services_router)
app.include_router(logs_router)
app.include_router(settings_router)
app.include_router(backup_router)
app.include_router(proxy_router)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9500, workers=4)
