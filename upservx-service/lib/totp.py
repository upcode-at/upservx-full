"""
TOTP (Time-based One-Time Password) management for 2FA.

Secrets are stored encrypted in /etc/upservx/2fa.json using the existing
EncryptionManager. Each entry maps a Linux username to its encrypted TOTP secret.
"""

import hashlib
import os
import secrets
import time
from typing import Optional

import pyotp

from lib.encryption import get_encryption_manager
from lib.file_lock import InterProcessFileLock
from lib.secure_store import secure_read_json, secure_write_json

_2FA_FILE = "/etc/upservx/2fa.json"

# ---------------------------------------------------------------------------
# Persistent store for pending setup sessions:
#   /etc/upservx/2fa_setup.json  ->  {token: {username, secret, expires}}
# ---------------------------------------------------------------------------
_SETUP_FILE = "/etc/upservx/2fa_setup.json"
_PENDING_TTL = 300  # 5 minutes


def _store_lock(path: str) -> InterProcessFileLock:
    return InterProcessFileLock(f"{path}.lock")


def _load_pending() -> dict:
    value = secure_read_json(_SETUP_FILE, missing={})
    if not isinstance(value, dict):
        raise ValueError("Invalid pending 2FA setup store")
    return value


def _save_pending(store: dict) -> None:
    secure_write_json(_SETUP_FILE, store)


def _cleanup_pending_store(store: dict) -> dict:
    now = time.time()
    cleaned = {}
    for token_or_hash, entry in store.items():
        if not isinstance(entry, dict) or entry.get("expires", 0) <= now:
            continue
        token_hash = (
            token_or_hash
            if len(token_or_hash) == 64
            and all(character in "0123456789abcdef" for character in token_or_hash)
            else hashlib.sha256(token_or_hash.encode("utf-8")).hexdigest()
        )
        cleaned[token_hash] = entry
    return cleaned

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

    with _store_lock(_SETUP_FILE):
        store = _load_pending()
        store = _cleanup_pending_store(store)
        store[hashlib.sha256(token.encode("utf-8")).hexdigest()] = {
            "username": username,
            "encrypted_secret": get_encryption_manager().encrypt(secret),
            "expires": expires,
        }
        _save_pending(store)

    totp = pyotp.TOTP(secret)
    hostname = os.uname().nodename
    uri = totp.provisioning_uri(name=username, issuer_name=f"UpservX ({hostname})")
    return token, uri


def verify_and_activate(token: str, code: str) -> bool:
    """
    Verify the TOTP code for a pending setup session and, if valid, persist
    the secret and remove the pending entry.

    Returns True on success, False on invalid/expired token or wrong code.
    """
    with _store_lock(_SETUP_FILE):
        store = _load_pending()
        store = _cleanup_pending_store(store)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        entry = store.get(token_hash)
        if not entry:
            _save_pending(store)
            return False

        encrypted_secret = entry.get("encrypted_secret")
        if not encrypted_secret:
            raise ValueError("Pending 2FA secret is not encrypted")
        secret = get_encryption_manager().decrypt(encrypted_secret)
        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            _save_pending(store)
            return False

        # Valid – persist the secret, remove the pending entry
        _save_secret(entry["username"], secret)
        del store[token_hash]
        _save_pending(store)
        return True


def cancel_pending(token: str) -> None:
    """Discard a pending setup session."""
    with _store_lock(_SETUP_FILE):
        store = _load_pending()
        store = _cleanup_pending_store(store)
        store.pop(hashlib.sha256(token.encode("utf-8")).hexdigest(), None)
        _save_pending(store)


# ---------------------------------------------------------------------------
# Persistent secret storage
# ---------------------------------------------------------------------------

def _load_store() -> dict:
    """Load the encrypted 2FA store and fail closed if it is corrupt."""
    value = secure_read_json(_2FA_FILE, missing={})
    if not isinstance(value, dict):
        raise ValueError("Invalid 2FA store")
    return value


def _save_store(store: dict) -> None:
    """Persist the 2FA store atomically."""
    secure_write_json(_2FA_FILE, store)


def _save_secret(username: str, secret: str) -> None:
    """Encrypt and store a TOTP secret for the given user."""
    enc = get_encryption_manager()
    with _store_lock(_2FA_FILE):
        store = _load_store()
        store[username] = enc.encrypt(secret)
        _save_store(store)


def get_secret(username: str) -> Optional[str]:
    """Return the plaintext TOTP secret for *username*, or None if not set."""
    with _store_lock(_2FA_FILE):
        store = _load_store()
    encrypted = store.get(username)
    if not encrypted:
        return None
    return get_encryption_manager().decrypt(encrypted)


def disable_2fa(username: str) -> None:
    """Remove the stored TOTP secret for *username*."""
    with _store_lock(_2FA_FILE):
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
#   /etc/upservx/login_tokens.json  ->  {token_hash: {username, expires, attempts}}
# ---------------------------------------------------------------------------
_LOGIN_TOKENS_FILE = "/etc/upservx/login_tokens.json"
_LOGIN_TOKEN_TTL = 120  # 2 minutes


def _load_login_tokens() -> dict:
    value = secure_read_json(_LOGIN_TOKENS_FILE, missing={})
    if not isinstance(value, dict):
        raise ValueError("Invalid 2FA login token store")
    return value


def _save_login_tokens(store: dict) -> None:
    secure_write_json(_LOGIN_TOKENS_FILE, store)


def _cleanup_login_tokens(store: dict) -> dict:
    """Remove expired entries and return the cleaned dict."""
    now = time.time()
    return {t: e for t, e in store.items() if e.get("expires", 0) > now}


def _login_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _sanitize_login_tokens(store: dict) -> dict:
    """Drop legacy passwords and hash legacy plaintext token identifiers."""

    cleaned = _cleanup_login_tokens(store)
    sanitized = {}
    for token_or_hash, entry in cleaned.items():
        if not isinstance(entry, dict) or not entry.get("username"):
            continue
        token_hash = (
            token_or_hash
            if len(token_or_hash) == 64
            and all(character in "0123456789abcdef" for character in token_or_hash)
            else _login_token_hash(token_or_hash)
        )
        sanitized[token_hash] = {
            "username": entry["username"],
            "expires": entry.get("expires", 0),
            "attempts": int(entry.get("attempts", 0)),
            "first_factor_at": entry.get("first_factor_at", time.time()),
        }
    return sanitized


def migrate_login_token_store() -> None:
    """Remove any password-bearing legacy entries immediately at startup."""

    if not os.path.exists(_LOGIN_TOKENS_FILE):
        return
    with _store_lock(_LOGIN_TOKENS_FILE):
        _save_login_tokens(_sanitize_login_tokens(_load_login_tokens()))


def create_login_token(username: str) -> str:
    """
    Issue a short-lived token after successful password verification
    when 2FA is required. Successful PAM authentication is represented only by
    the username, issuance time, and an expiring random token hash.
    """
    token = secrets.token_urlsafe(48)
    expires = time.time() + _LOGIN_TOKEN_TTL
    with _store_lock(_LOGIN_TOKENS_FILE):
        store = _sanitize_login_tokens(_load_login_tokens())
        store[_login_token_hash(token)] = {
            "username": username,
            "expires": expires,
            "attempts": 0,
            "first_factor_at": time.time(),
        }
        _save_login_tokens(store)
    return token


def consume_login_token(token: str, code: str) -> Optional[str]:
    """
    Verify the TOTP code for a login token.

    Returns the username on success, or None if the token is invalid, expired,
    over its attempt limit, or accompanied by the wrong code.
    """
    with _store_lock(_LOGIN_TOKENS_FILE):
        store = _sanitize_login_tokens(_load_login_tokens())
        token_hash = _login_token_hash(token)
        entry = store.get(token_hash)
        if not entry:
            _save_login_tokens(store)
            return None
        username = entry["username"]
        if not verify_code(username, code):
            entry["attempts"] = int(entry.get("attempts", 0)) + 1
            if entry["attempts"] >= 5:
                del store[token_hash]
            _save_login_tokens(store)
            return None
        del store[token_hash]
        _save_login_tokens(store)
    return username
