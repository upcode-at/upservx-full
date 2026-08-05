"""Revocable, hashed API tokens with explicit roles and scopes."""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from lib.secure_store import ensure_config_directory, secure_read_json, secure_write_json


API_TOKENS_FILE = os.getenv(
    "UPSERVX_API_TOKENS_FILE",
    "/etc/upservx/api_tokens.json",
)
API_TOKENS_LOCK_FILE = os.getenv(
    "UPSERVX_API_TOKENS_LOCK_FILE",
    "/etc/upservx/api_tokens.lock",
)
ALLOWED_TOKEN_ROLES = {"admin", "operator", "read-only"}


@dataclass(frozen=True)
class ApiTokenPrincipal:
    token_id: str
    name: str
    role: str
    scopes: frozenset[str]
    expires_at: int | None

    @property
    def username(self) -> str:
        return f"api-token:{self.token_id}"


class _TokenLock:
    def __enter__(self):
        path = Path(API_TOKENS_LOCK_FILE)
        ensure_config_directory(path.parent)
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        os.fchmod(fd, 0o600)
        self.file = os.fdopen(fd, "a+", encoding="utf-8")
        fcntl.flock(self.file.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.file.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _load_store() -> dict:
    value = secure_read_json(API_TOKENS_FILE, missing={"tokens": []})
    if not isinstance(value, dict) or not isinstance(value.get("tokens", []), list):
        raise RuntimeError("Invalid API token store")
    value.setdefault("tokens", [])
    return value


def _normalize_scopes(scopes: Iterable[str]) -> list[str]:
    normalized = sorted({str(scope).strip() for scope in scopes if str(scope).strip()})
    if not normalized:
        raise ValueError("At least one API token scope is required")
    for scope in normalized:
        if len(scope) > 128 or any(character.isspace() for character in scope):
            raise ValueError("Invalid API token scope")
    return normalized


def create_api_token(
    name: str,
    role: str,
    scopes: Iterable[str],
    *,
    expires_in: int | None = None,
) -> tuple[str, dict]:
    """Create a token, returning its plaintext exactly once and safe metadata."""

    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 128:
        raise ValueError("API token name must contain 1 to 128 characters")
    if role not in ALLOWED_TOKEN_ROLES:
        raise ValueError("Invalid API token role")
    normalized_scopes = _normalize_scopes(scopes)
    if expires_in is not None and not 300 <= int(expires_in) <= 31_536_000:
        raise ValueError("API token expiry must be between 5 minutes and 1 year")

    token_id = secrets.token_urlsafe(12)
    token = f"upx_{token_id}.{secrets.token_urlsafe(32)}"
    now = int(time.time())
    entry = {
        "id": token_id,
        "name": normalized_name,
        "token_hash": _token_hash(token),
        "role": role,
        "scopes": normalized_scopes,
        "created_at": _now_iso(),
        "expires_at": now + int(expires_in) if expires_in is not None else None,
        "revoked_at": None,
    }
    with _TokenLock():
        store = _load_store()
        store["tokens"].append(entry)
        secure_write_json(API_TOKENS_FILE, store)
    return token, _public_entry(entry)


def _public_entry(entry: dict) -> dict:
    return {
        key: entry.get(key)
        for key in (
            "id",
            "name",
            "role",
            "scopes",
            "created_at",
            "expires_at",
            "revoked_at",
        )
    }


def list_api_tokens() -> list[dict]:
    with _TokenLock():
        store = _load_store()
    return [_public_entry(entry) for entry in store["tokens"] if isinstance(entry, dict)]


def verify_api_token(token: str) -> ApiTokenPrincipal | None:
    """Verify a high-entropy token against stored hashes and revocation state."""

    if not token or len(token) > 512:
        return None
    supplied_hash = _token_hash(token)
    now = int(time.time())
    with _TokenLock():
        entries = _load_store()["tokens"]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        stored_hash = str(entry.get("token_hash", ""))
        if not stored_hash or not hmac.compare_digest(stored_hash, supplied_hash):
            continue
        expires_at = entry.get("expires_at")
        if entry.get("revoked_at"):
            return None
        if expires_at is not None and int(expires_at) <= now:
            return None
        role = str(entry.get("role", ""))
        if role not in ALLOWED_TOKEN_ROLES:
            return None
        scopes = entry.get("scopes", [])
        if not isinstance(scopes, list) or not scopes:
            return None
        token_id = str(entry.get("id", ""))
        if not token_id:
            return None
        return ApiTokenPrincipal(
            token_id=token_id,
            name=str(entry.get("name", "")),
            role=role,
            scopes=frozenset(str(scope) for scope in scopes),
            expires_at=int(expires_at) if expires_at is not None else None,
        )
    return None


def revoke_api_token(token_id: str) -> bool:
    """Mark a token revoked while retaining audit metadata."""

    with _TokenLock():
        store = _load_store()
        for entry in store["tokens"]:
            if not isinstance(entry, dict) or entry.get("id") != token_id:
                continue
            if not entry.get("revoked_at"):
                entry["revoked_at"] = _now_iso()
                secure_write_json(API_TOKENS_FILE, store)
            return True
    return False


def migrate_legacy_api_key(settings_path: str | Path) -> bool:
    """Hash a legacy plaintext settings key and remove it from settings."""

    path = Path(settings_path)
    if not path.exists():
        return False
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Unable to migrate legacy API key")
    try:
        with path.open("r", encoding="utf-8") as file:
            settings = json.load(file)
    except (OSError, ValueError, TypeError) as error:
        raise RuntimeError("Unable to migrate legacy API key") from error
    legacy_key = settings.get("api_key") if isinstance(settings, dict) else None
    if not isinstance(legacy_key, str) or not legacy_key:
        return False

    supplied_hash = _token_hash(legacy_key)
    with _TokenLock():
        store = _load_store()
        if not any(
            isinstance(entry, dict)
            and hmac.compare_digest(str(entry.get("token_hash", "")), supplied_hash)
            for entry in store["tokens"]
        ):
            existing_ids = {
                str(entry.get("id"))
                for entry in store["tokens"]
                if isinstance(entry, dict) and entry.get("id")
            }
            token_id = "legacy"
            if token_id in existing_ids:
                token_id = f"legacy-{supplied_hash[:12]}"
            store["tokens"].append(
                {
                    "id": token_id,
                    "name": "Migrated legacy API key",
                    "token_hash": supplied_hash,
                    "role": "admin",
                    "scopes": ["*"],
                    "created_at": _now_iso(),
                    "expires_at": None,
                    "revoked_at": None,
                }
            )
            secure_write_json(API_TOKENS_FILE, store)
    settings.pop("api_key", None)
    secure_write_json(path, settings)
    return True
