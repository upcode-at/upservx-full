"""Signed, expiring, and server-revocable user sessions."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from lib.secure_store import (
    ensure_config_directory,
    secure_read_json,
    secure_write_bytes,
    secure_write_json,
)


SESSION_SECRET_FILE = os.getenv(
    "UPSERVX_SESSION_SECRET_FILE",
    "/etc/upservx/.session_secret",
)
SESSION_STORE_FILE = os.getenv(
    "UPSERVX_SESSION_STORE_FILE",
    "/etc/upservx/sessions.json",
)
SESSION_LOCK_FILE = os.getenv(
    "UPSERVX_SESSION_LOCK_FILE",
    "/etc/upservx/sessions.lock",
)
_SECRET_CACHE: bytes | None = None


class SessionStoreError(RuntimeError):
    """Raised when session security state is unavailable or invalid."""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _get_secret() -> bytes:
    """Load or persist the signing secret; never fall back to process memory."""

    global _SECRET_CACHE
    if _SECRET_CACHE is not None:
        return _SECRET_CACHE

    env_secret = os.getenv("UPSERVX_SESSION_SECRET", "").strip()
    if env_secret:
        if len(env_secret.encode("utf-8")) < 32:
            raise SessionStoreError("UPSERVX_SESSION_SECRET must contain at least 32 bytes")
        _SECRET_CACHE = env_secret.encode("utf-8")
        return _SECRET_CACHE

    secret_path = Path(SESSION_SECRET_FILE)
    old_file = secret_path.with_name("session_secret")
    try:
        if old_file != secret_path and old_file.is_file() and not secret_path.exists():
            os.replace(old_file, secret_path)
            os.chmod(secret_path, 0o600)

        if secret_path.is_file():
            if secret_path.is_symlink():
                raise SessionStoreError("Unsafe session secret path")
            secret = secret_path.read_bytes().strip()
            if len(secret) < 32:
                raise SessionStoreError("Session signing secret is invalid")
            os.chmod(secret_path, 0o600)
            _SECRET_CACHE = secret
            return secret

        secret = secrets.token_urlsafe(48).encode("utf-8")
        secure_write_bytes(secret_path, secret)
        _SECRET_CACHE = secret
        return secret
    except SessionStoreError:
        raise
    except OSError as error:
        raise SessionStoreError("Session signing secret is unavailable") from error


def _session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _load_sessions() -> dict:
    value = secure_read_json(SESSION_STORE_FILE, missing={})
    if not isinstance(value, dict):
        raise SessionStoreError("Invalid session store")
    return value


def _cleanup_sessions(store: dict, now: int) -> dict:
    return {
        key: entry
        for key, entry in store.items()
        if isinstance(entry, dict) and int(entry.get("expires", 0)) > now
    }


class _SessionLock:
    def __enter__(self):
        lock_path = Path(SESSION_LOCK_FILE)
        ensure_config_directory(lock_path.parent)
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        os.fchmod(fd, 0o600)
        self.file = os.fdopen(fd, "a+", encoding="utf-8")
        fcntl.flock(self.file.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()


def _decode_verified_payload(token: str) -> dict | None:
    if not token or len(token) > 4096:
        return None
    try:
        payload_b64, signature_b64 = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_b64)
        supplied_signature = _b64url_decode(signature_b64)
        expected_signature = hmac.new(
            _get_secret(),
            payload_bytes,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        payload = json.loads(payload_bytes.decode("utf-8"))
        return payload if isinstance(payload, dict) else None
    except SessionStoreError:
        raise
    except Exception:
        return None


def create_session_token(username: str, ttl_seconds: int = 3600) -> str:
    """Create and register a signed session token."""

    normalized_username = username.strip()
    if not normalized_username:
        raise ValueError("Session username is required")
    issued_at = int(time.time())
    expires = issued_at + max(1, int(ttl_seconds))
    session_id = secrets.token_urlsafe(32)
    payload = {
        "u": normalized_username,
        "i": issued_at,
        "e": expires,
        "s": session_id,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(_get_secret(), payload_bytes, hashlib.sha256).digest()

    with _SessionLock():
        sessions = _cleanup_sessions(_load_sessions(), issued_at)
        sessions[_session_hash(session_id)] = {
            "username": normalized_username,
            "issued_at": issued_at,
            "expires": expires,
        }
        secure_write_json(SESSION_STORE_FILE, sessions)
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"


def verify_session_token(token: str) -> str | None:
    """Verify signature, expiry, and server-side revocation state."""

    payload = _decode_verified_payload(token)
    if not payload:
        return None
    try:
        username = str(payload["u"]).strip()
        expires = int(payload["e"])
        session_id = str(payload["s"])
    except (KeyError, TypeError, ValueError):
        return None
    now = int(time.time())
    if not username or not session_id or expires <= now:
        return None

    with _SessionLock():
        sessions = _cleanup_sessions(_load_sessions(), now)
        entry = sessions.get(_session_hash(session_id))
        secure_write_json(SESSION_STORE_FILE, sessions)
    if not entry:
        return None
    if not hmac.compare_digest(str(entry.get("username", "")), username):
        return None
    if int(entry.get("expires", 0)) != expires:
        return None
    return username


def revoke_session_token(token: str) -> bool:
    """Revoke one session immediately."""

    payload = _decode_verified_payload(token)
    if not payload or not payload.get("s"):
        return False
    session_key = _session_hash(str(payload["s"]))
    with _SessionLock():
        sessions = _cleanup_sessions(_load_sessions(), int(time.time()))
        existed = sessions.pop(session_key, None) is not None
        secure_write_json(SESSION_STORE_FILE, sessions)
    return existed


def revoke_user_sessions(username: str, *, except_token: str | None = None) -> int:
    """Revoke all sessions for a user, optionally preserving one token."""

    preserved_hash = None
    if except_token:
        payload = _decode_verified_payload(except_token)
        if payload and payload.get("s"):
            preserved_hash = _session_hash(str(payload["s"]))
    revoked = 0
    with _SessionLock():
        sessions = _cleanup_sessions(_load_sessions(), int(time.time()))
        for session_key, entry in list(sessions.items()):
            if session_key == preserved_hash:
                continue
            if hmac.compare_digest(str(entry.get("username", "")), username):
                del sessions[session_key]
                revoked += 1
        secure_write_json(SESSION_STORE_FILE, sessions)
    return revoked
