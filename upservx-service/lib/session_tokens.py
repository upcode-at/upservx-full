"""Signed session tokens for user authentication.

Token format: base64url(payload).base64url(signature)
payload: {"u": "<username>", "e": <unix_expiry_seconds>}
signature: HMAC-SHA256(secret, payload_bytes)
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time


SESSION_SECRET_FILE = "/etc/upservx/session_secret"
_SECRET_CACHE: bytes | None = None


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _get_secret() -> bytes:
    global _SECRET_CACHE
    if _SECRET_CACHE is not None:
        return _SECRET_CACHE

    env_secret = os.getenv("UPSERVX_SESSION_SECRET", "").strip()
    if env_secret:
        _SECRET_CACHE = env_secret.encode()
        return _SECRET_CACHE

    try:
        os.makedirs("/etc/upservx", exist_ok=True)
        if os.path.isfile(SESSION_SECRET_FILE):
            with open(SESSION_SECRET_FILE, "rb") as f:
                secret = f.read().strip()
                if secret:
                    _SECRET_CACHE = secret
                    return _SECRET_CACHE

        secret = secrets.token_urlsafe(48).encode()
        with open(SESSION_SECRET_FILE, "wb") as f:
            f.write(secret)
        os.chmod(SESSION_SECRET_FILE, 0o600)
        _SECRET_CACHE = secret
        return _SECRET_CACHE
    except Exception:
        # Last-resort in-memory secret. Tokens survive until process restart.
        _SECRET_CACHE = secrets.token_urlsafe(48).encode()
        return _SECRET_CACHE


def create_session_token(username: str, ttl_seconds: int = 3600) -> str:
    expires = int(time.time()) + max(1, int(ttl_seconds))
    payload = {"u": username, "e": expires}
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(_get_secret(), payload_bytes, hashlib.sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(sig)}"


def verify_session_token(token: str) -> str | None:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_b64)
        given_sig = _b64url_decode(sig_b64)
        expected_sig = hmac.new(_get_secret(), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(given_sig, expected_sig):
            return None

        payload = json.loads(payload_bytes.decode())
        username = str(payload.get("u", "")).strip()
        expires = int(payload.get("e", 0))
        if not username or expires < int(time.time()):
            return None
        return username
    except Exception:
        return None
