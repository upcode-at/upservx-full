"""Authentication and system shell routes."""

import asyncio
import os
import pty
import pam
import platform
import subprocess
import threading
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, WebSocket
from fastapi.responses import Response
from starlette.websockets import WebSocketDisconnect

from lib.ws_tickets import create_ticket as _create_ws_ticket, consume_ticket as _consume_ws_ticket
from lib.permissions import get_user_groups, get_permission_summary, has_shell_access
from lib.session_tokens import create_session_token, verify_session_token
from lib.logger import log_auth
from handlers.settings import load_settings
import lib.totp as totp_lib

router = APIRouter()

pam_auth = pam.pam()

# ---------------------------------------------------------------------------
# Generic in-memory rate limiter
# ---------------------------------------------------------------------------
_rl_buckets: dict = defaultdict(list)
_rl_lock = threading.Lock()


def _check_rate_limit(key: str, max_attempts: int, window_seconds: int) -> bool:
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_seconds)
    with _rl_lock:
        attempts = [t for t in _rl_buckets[key] if t > cutoff]
        _rl_buckets[key] = attempts
        if len(attempts) >= max_attempts:
            return False
        _rl_buckets[key].append(now)
        return True


def _check_login_rate_limit(ip: str) -> bool:
    return _check_rate_limit(f"login:{ip}", max_attempts=10, window_seconds=60)


def _check_ws_ticket_rate_limit(ip: str) -> bool:
    return _check_rate_limit(f"ws_ticket:{ip}", max_attempts=20, window_seconds=60)


@router.post("/auth/login")
async def auth_login(payload: dict, request: Request):
    """Login – sets an HttpOnly signed session-token cookie."""
    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password required")

    client_ip = request.client.host if request.client else "unknown"
    if not _check_login_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="too many login attempts")

    settings = load_settings()
    if settings.deny_root_login and username == "root":
        log_auth(f"Root login blocked for [{username}] from {client_ip}", error=True)
        raise HTTPException(status_code=403, detail="root login is disabled")

    try:
        if pam_auth.authenticate(username, password):
            # Check if 2FA is enabled for this user
            if totp_lib.is_enabled(username):
                login_token = totp_lib.create_login_token(username, password)
                log_auth(f"2FA required for user [{username}] from {client_ip}")
                return Response(
                    content=f'{{"2fa_required": true, "login_token": "{login_token}"}}',
                    media_type="application/json",
                    status_code=200,
                )
            token = create_session_token(username, ttl_seconds=3600)
            resp = Response(
                content=f'{{"detail": "logged_in", "session_token": "{token}", "expires_in": 3600}}',
                media_type="application/json",
            )
            resp.set_cookie("auth", token, httponly=True, samesite="Lax", max_age=3600)
            log_auth(f"Login successful for user [{username}] from {client_ip}")
            return resp
        else:
            log_auth(f"Login failed for user [{username}] from {client_ip}", error=True)
            raise HTTPException(status_code=401, detail="invalid credentials")
    except HTTPException:
        raise
    except Exception:
        log_auth(f"Login error for user [{username}] from {client_ip}", error=True)
        raise HTTPException(status_code=401, detail="invalid credentials")


@router.post("/auth/2fa/complete")
async def auth_2fa_complete(payload: dict, request: Request):
    """Complete login after 2FA verification. Consumes the temp login_token."""
    login_token = payload.get("login_token", "")
    code = payload.get("code", "")
    client_ip = request.client.host if request.client else "unknown"

    if not login_token or not code:
        raise HTTPException(status_code=400, detail="login_token and code required")

    result = totp_lib.consume_login_token(login_token, code)
    if not result:
        log_auth(f"2FA verification failed from {client_ip}", error=True)
        raise HTTPException(status_code=401, detail="invalid or expired 2FA code")

    username, _password = result
    auth_token = create_session_token(username, ttl_seconds=3600)
    resp = Response(
        content=f'{{"detail": "logged_in", "session_token": "{auth_token}", "expires_in": 3600}}',
        media_type="application/json",
    )
    resp.set_cookie("auth", auth_token, httponly=True, samesite="Lax", max_age=3600)
    log_auth(f"2FA login successful for user [{username}] from {client_ip}")
    return resp


@router.post("/auth/logout")
async def auth_logout():
    resp = Response(content='{"detail": "logged_out"}', media_type="application/json")
    resp.delete_cookie("auth")
    return resp


@router.get("/auth/ws-ticket")
async def get_ws_ticket(request: Request):
    """Issue a short-lived one-time token for WebSocket authentication."""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_ws_ticket_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="too many ticket requests")
    username = getattr(request.state, "user", None) or "authenticated"
    try:
        ticket = _create_ws_ticket(username)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="ticket store full — try again shortly")
    return {"ticket": ticket}


@router.get("/auth/me")
def auth_me(request: Request):
    """Return the current user's username, Linux groups and derived permissions."""
    username = getattr(request.state, "user", None) or "unknown"
    groups = getattr(request.state, "groups", None)
    if groups is None:
        groups = get_user_groups(username)
    return get_permission_summary(username, groups)


# ---------------------------------------------------------------------------
# 2FA management endpoints (all require authentication)
# ---------------------------------------------------------------------------

@router.get("/auth/2fa/status")
def auth_2fa_status(request: Request):
    """Return whether 2FA is enabled for the current user."""
    username = getattr(request.state, "user", None)
    if not username or username in ("api-key", "cluster-node", "cluster-master"):
        raise HTTPException(status_code=403, detail="not allowed for this auth method")
    return {"enabled": totp_lib.is_enabled(username)}


@router.post("/auth/2fa/setup")
def auth_2fa_setup(request: Request):
    """Begin 2FA setup: generate a new TOTP secret and return the provisioning URI."""
    username = getattr(request.state, "user", None)
    if not username or username in ("api-key", "cluster-node", "cluster-master"):
        raise HTTPException(status_code=403, detail="not allowed for this auth method")
    if totp_lib.is_enabled(username):
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    setup_token, uri = totp_lib.create_pending_setup(username)
    return {"setup_token": setup_token, "uri": uri}


@router.post("/auth/2fa/verify-setup")
def auth_2fa_verify_setup(payload: dict, request: Request):
    """Confirm 2FA setup by verifying the first TOTP code."""
    username = getattr(request.state, "user", None)
    if not username or username in ("api-key", "cluster-node", "cluster-master"):
        raise HTTPException(status_code=403, detail="not allowed for this auth method")
    setup_token = payload.get("setup_token", "")
    code = payload.get("code", "")
    if not setup_token or not code:
        raise HTTPException(status_code=400, detail="setup_token and code required")
    if not totp_lib.verify_and_activate(setup_token, code):
        raise HTTPException(status_code=400, detail="invalid or expired code")
    log_auth(f"2FA enabled for user [{username}]")
    return {"detail": "2FA enabled successfully"}


@router.post("/auth/2fa/disable")
def auth_2fa_disable(payload: dict, request: Request):
    """Disable 2FA for the current user (requires current password + TOTP code)."""
    username = getattr(request.state, "user", None)
    if not username or username in ("api-key", "cluster-node", "cluster-master"):
        raise HTTPException(status_code=403, detail="not allowed for this auth method")
    if not totp_lib.is_enabled(username):
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    password = payload.get("password", "")
    code = payload.get("code", "")
    if not password or not code:
        raise HTTPException(status_code=400, detail="password and code required")
    # Verify password
    _pam = pam.pam()
    if not _pam.authenticate(username, password):
        raise HTTPException(status_code=401, detail="password is incorrect")
    # Verify current TOTP code
    if not totp_lib.verify_code(username, code):
        raise HTTPException(status_code=401, detail="invalid 2FA code")
    totp_lib.disable_2fa(username)
    log_auth(f"2FA disabled for user [{username}]")
    return {"detail": "2FA disabled successfully"}


@router.post("/auth/change-password")
async def change_password(payload: dict, request: Request):
    """Change the current user's own password via PAM verification + chpasswd."""
    username = getattr(request.state, "user", None)
    if not username or username in ("api-key", "cluster-node", "cluster-master"):
        raise HTTPException(status_code=403, detail="not allowed for this auth method")

    current_password = payload.get("current_password", "")
    new_password = payload.get("new_password", "")

    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="current_password and new_password required")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="new password must be at least 8 characters")

    # Verify current password via PAM
    _pam = pam.pam()
    if not _pam.authenticate(username, current_password):
        log_auth(f"Password change failed (wrong current password) for user [{username}]", error=True)
        raise HTTPException(status_code=401, detail="current password is incorrect")

    # Change password using chpasswd
    try:
        proc = subprocess.run(
            ["chpasswd"],
            input=f"{username}:{new_password}",
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            log_auth(f"Password change failed for user [{username}]: {proc.stderr.strip()}", error=True)
            raise HTTPException(status_code=500, detail="failed to change password")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="password change timed out")

    log_auth(f"Password changed successfully for user [{username}]")
    return {"detail": "password changed successfully"}


@router.get("/info")
def server_info():
    """Return basic server information accessible to all authenticated users."""
    try:
        with open("/etc/hostname") as f:
            hostname = f.read().strip()
    except Exception:
        hostname = platform.node() or "server"
    return {"hostname": hostname}


@router.websocket("/system/shell")
async def system_shell_websocket(websocket: WebSocket):
    """Interactive shell access via WebSocket."""
    authenticated = False
    shell_username: str | None = None

    raw_token = websocket.query_params.get("token")
    if raw_token:
        ticket_user = _consume_ws_ticket(raw_token)
        if ticket_user:
            authenticated = True
            shell_username = ticket_user
        else:
            settings = load_settings()
            if settings.api_key and raw_token == settings.api_key:
                authenticated = True
                shell_username = "api-key"

    if not authenticated:
        auth_token = websocket.cookies.get("auth")
        if auth_token:
            try:
                if auth_token.lower().startswith("bearer "):
                    auth_token = auth_token[7:]
                ws_user = verify_session_token(auth_token)
                if ws_user:
                    authenticated = True
                    shell_username = ws_user
            except Exception:
                pass

    if not authenticated:
        await websocket.accept()
        await websocket.close(code=4401)
        return

    _shell_groups = get_user_groups(shell_username or "")
    if not has_shell_access(shell_username or "", _shell_groups):
        await websocket.accept()
        await websocket.close(code=4403)
        return

    import fcntl
    import struct
    import termios
    import json

    await websocket.accept()
    loop = asyncio.get_event_loop()
    master_fd: int | None = None
    pid: int | None = None

    try:
        master_fd, slave_fd = pty.openpty()
        pid = os.fork()

        if pid == 0:
            os.close(master_fd)
            os.setsid()
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            if slave_fd > 2:
                os.close(slave_fd)
            os.environ['TERM'] = 'xterm-256color'
            os.execvp("bash", ["bash", "-l"])
            os._exit(1)

        os.close(slave_fd)

        winsize = struct.pack("HHHH", 24, 80, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)

        async def read_from_pty():
            while True:
                try:
                    data = await loop.run_in_executor(None, os.read, master_fd, 4096)
                    if not data:
                        break
                    await websocket.send_text(data.decode('utf-8', errors='ignore'))
                except OSError:
                    break
                except Exception:
                    break

        async def write_to_pty():
            try:
                while True:
                    msg = await websocket.receive_text()
                    if msg.startswith("{"):
                        try:
                            obj = json.loads(msg)
                            if obj.get("type") == "resize":
                                rows = int(obj.get("rows", 24))
                                cols = int(obj.get("cols", 80))
                                ws_size = struct.pack("HHHH", rows, cols, 0, 0)
                                fcntl.ioctl(master_fd, termios.TIOCSWINSZ, ws_size)
                                continue
                        except Exception:
                            pass
                    os.write(master_fd, msg.encode('utf-8'))
            except WebSocketDisconnect:
                pass
            except Exception:
                pass

        await asyncio.gather(read_from_pty(), write_to_pty(), return_exceptions=True)

    except Exception as e:
        try:
            await websocket.send_text(f"Shell error: {str(e)}\r\n")
        except Exception:
            pass
    finally:
        if master_fd is not None:
            try:
                os.close(master_fd)
            except Exception:
                pass
        if pid is not None:
            try:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass
