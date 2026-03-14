"""
TOTP (Time-based One-Time Password) management for 2FA.

Secrets are stored encrypted in /etc/upservx/2fa.json using the existing
EncryptionManager. Each entry maps a Linux username to its encrypted TOTP secret.
"""

import json
import os
import secrets
import threading
import time
from typing import Optional

import pyotp

from lib.encryption import get_encryption_manager

_2FA_FILE = "/etc/upservx/2fa.json"
_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Persistent store for pending setup sessions:
#   /etc/upservx/2fa_setup.json  ->  {token: {username, secret, expires}}
# ---------------------------------------------------------------------------
_SETUP_FILE = "/etc/upservx/2fa_setup.json"
_pending_lock = threading.Lock()
_PENDING_TTL = 300  # 5 minutes


def _load_pending() -> dict:
    if not os.path.exists(_SETUP_FILE):
        return {}
    try:
        with open(_SETUP_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_pending(store: dict) -> None:
    os.makedirs(os.path.dirname(_SETUP_FILE), exist_ok=True)
    tmp = _SETUP_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, _SETUP_FILE)


def _cleanup_pending_store(store: dict) -> dict:
    now = time.time()
    return {t: e for t, e in store.items() if e.get("expires", 0) > now}

def create_pending_setup(username: str) -> tuple[str, str]:
    """
    Generate a new TOTP secret and store it in the pending-setup store.

    Returns:
        (token, provisioning_uri) – the token identifies this setup session,
        the URI encodes the secret for QR-code display.
    """
    secret = pyotp.random_base32()
    token = secrets.token_urlsafe(32)
    expires = time.time() + _PENDING_TTL

    with _pending_lock:
        store = _load_pending()
        store = _cleanup_pending_store(store)
        store[token] = {"username": username, "secret": secret, "expires": expires}
        _save_pending(store)

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=username, issuer_name="UpservX")
    return token, uri


def verify_and_activate(token: str, code: str) -> bool:
    """
    Verify the TOTP code for a pending setup session and, if valid, persist
    the secret and remove the pending entry.

    Returns True on success, False on invalid/expired token or wrong code.
    """
    with _pending_lock:
        store = _load_pending()
        store = _cleanup_pending_store(store)
        entry = store.get(token)
        if not entry:
            return False

        totp = pyotp.TOTP(entry["secret"])
        if not totp.verify(code, valid_window=1):
            return False

        # Valid – persist the secret, remove the pending entry
        _save_secret(entry["username"], entry["secret"])
        del store[token]
        _save_pending(store)
        return True


def cancel_pending(token: str) -> None:
    """Discard a pending setup session."""
    with _pending_lock:
        store = _load_pending()
        store.pop(token, None)
        _save_pending(store)


# ---------------------------------------------------------------------------
# Persistent secret storage
# ---------------------------------------------------------------------------

def _load_store() -> dict:
    """Load the encrypted 2FA store. Returns {} if not found or corrupt."""
    if not os.path.exists(_2FA_FILE):
        return {}
    try:
        with open(_2FA_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_store(store: dict) -> None:
    """Persist the 2FA store atomically."""
    os.makedirs(os.path.dirname(_2FA_FILE), exist_ok=True)
    tmp = _2FA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, _2FA_FILE)


def _save_secret(username: str, secret: str) -> None:
    """Encrypt and store a TOTP secret for the given user."""
    enc = get_encryption_manager()
    with _lock:
        store = _load_store()
        store[username] = enc.encrypt(secret)
        _save_store(store)


def get_secret(username: str) -> Optional[str]:
    """Return the plaintext TOTP secret for *username*, or None if not set."""
    with _lock:
        store = _load_store()
    encrypted = store.get(username)
    if not encrypted:
        return None
    try:
        return get_encryption_manager().decrypt(encrypted)
    except Exception:
        return None


def disable_2fa(username: str) -> None:
    """Remove the stored TOTP secret for *username*."""
    with _lock:
        store = _load_store()
        store.pop(username, None)
        _save_store(store)


def is_enabled(username: str) -> bool:
    """Return True if 2FA is enabled for *username*."""
    return get_secret(username) is not None


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_code(username: str, code: str) -> bool:
    """
    Verify a TOTP code for *username*.
    Accepts codes from the previous and next 30-second window (valid_window=1).
    """
    secret = get_secret(username)
    if not secret:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# ---------------------------------------------------------------------------
# Persistent store for login temp-tokens (pending 2FA after password auth).
# Persisted to disk so all uvicorn worker processes share the same state.
#   /etc/upservx/login_tokens.json  ->  {token: {username, enc_password, expires}}
# ---------------------------------------------------------------------------
_LOGIN_TOKENS_FILE = "/etc/upservx/login_tokens.json"
_login_tokens_lock = threading.Lock()
_LOGIN_TOKEN_TTL = 120  # 2 minutes


def _load_login_tokens() -> dict:
    if not os.path.exists(_LOGIN_TOKENS_FILE):
        return {}
    try:
        with open(_LOGIN_TOKENS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_login_tokens(store: dict) -> None:
    os.makedirs(os.path.dirname(_LOGIN_TOKENS_FILE), exist_ok=True)
    tmp = _LOGIN_TOKENS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(store, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, _LOGIN_TOKENS_FILE)


def _cleanup_login_tokens(store: dict) -> dict:
    """Remove expired entries and return the cleaned dict."""
    now = time.time()
    return {t: e for t, e in store.items() if e.get("expires", 0) > now}


def create_login_token(username: str, password: str) -> str:
    """
    Issue a short-lived token after successful password verification
    when 2FA is required. The password is stored encrypted so the auth cookie
    can be constructed once 2FA is verified.
    """
    enc = get_encryption_manager()
    token = secrets.token_urlsafe(48)
    expires = time.time() + _LOGIN_TOKEN_TTL
    enc_password = enc.encrypt(password)
    with _login_tokens_lock:
        store = _load_login_tokens()
        store = _cleanup_login_tokens(store)
        store[token] = {"username": username, "enc_password": enc_password, "expires": expires}
        _save_login_tokens(store)
    return token


def consume_login_token(token: str, code: str) -> Optional[tuple[str, str]]:
    """
    Verify the TOTP code for a login token.

    Returns (username, password) on success so the caller can set the auth
    cookie, or None if the token is invalid/expired or the code is wrong.
    """
    enc = get_encryption_manager()
    with _login_tokens_lock:
        store = _load_login_tokens()
        store = _cleanup_login_tokens(store)
        entry = store.get(token)
        if not entry:
            return None
        username = entry["username"]
        enc_password = entry["enc_password"]
        # Verify TOTP before consuming
        if not verify_code(username, code):
            return None
        # Consume – remove token immediately
        del store[token]
        _save_login_tokens(store)

    try:
        password = enc.decrypt(enc_password)
    except Exception:
        return None
    return username, password
