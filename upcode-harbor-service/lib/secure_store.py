"""Centralized secure persistence for files under the Upcode Harbor config root."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


CONFIG_ROOT = Path(os.getenv("UPCODE_HARBOR_CONFIG_DIR", "/etc/upcode-harbor"))
CONFIG_DIRECTORY_MODE = 0o700
CONFIG_FILE_MODE = 0o600


class SecureStoreError(RuntimeError):
    """Raised when security-sensitive configuration cannot be persisted."""


def apply_secure_umask() -> int:
    """Ensure all subsequently created service files default to owner-only."""

    return os.umask(0o077)


def _resolved(path: str | Path) -> Path:
    candidate = Path(path)
    was_relative = not candidate.is_absolute()
    if was_relative:
        candidate = CONFIG_ROOT / candidate
    # Normalize `..` without resolving symlinks. Callers must still be able to
    # detect and reject links instead of silently following them.
    resolved = Path(os.path.abspath(candidate))
    if was_relative:
        root = Path(os.path.abspath(CONFIG_ROOT))
        if resolved != root and root not in resolved.parents:
            raise SecureStoreError("Relative configuration path escapes its root")
    return resolved


def _reject_symlink_components(path: Path) -> None:
    """Reject an existing symlink anywhere in a security-sensitive path."""

    for component in (path, *path.parents):
        if component.is_symlink():
            raise SecureStoreError(f"Unsafe configuration link {component}")


def ensure_config_directory(path: str | Path | None = None) -> Path:
    """Create and lock down a configuration directory."""

    resolved = _resolved(CONFIG_ROOT if path is None else path)
    try:
        _reject_symlink_components(resolved)
        if resolved.is_symlink() or (resolved.exists() and not resolved.is_dir()):
            raise SecureStoreError(f"Unsafe configuration directory {resolved}")
        resolved.mkdir(parents=True, exist_ok=True, mode=CONFIG_DIRECTORY_MODE)
        current = resolved
        root = _resolved(CONFIG_ROOT)
        while current == root or root in current.parents:
            if current.is_symlink() or not current.is_dir():
                raise SecureStoreError(f"Unsafe configuration directory {current}")
            os.chmod(current, CONFIG_DIRECTORY_MODE)
            if current == root:
                break
            current = current.parent
        return resolved
    except SecureStoreError:
        raise
    except OSError as error:
        raise SecureStoreError(f"Unable to secure configuration directory {resolved}") from error


def secure_write_bytes(path: str | Path, value: bytes) -> None:
    """Atomically write an owner-only configuration file."""

    resolved = _resolved(path)
    ensure_config_directory(resolved.parent)
    temporary_path: str | None = None
    try:
        fd, temporary_path = tempfile.mkstemp(
            prefix=f".{resolved.name}.",
            dir=str(resolved.parent),
        )
        os.fchmod(fd, CONFIG_FILE_MODE)
        with os.fdopen(fd, "wb") as file:
            file.write(value)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, resolved)
        temporary_path = None
        os.chmod(resolved, CONFIG_FILE_MODE)
    except OSError as error:
        raise SecureStoreError(f"Unable to persist configuration file {resolved}") from error
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass


def secure_write_text(path: str | Path, value: str) -> None:
    secure_write_bytes(path, value.encode("utf-8"))


def secure_write_json(path: str | Path, value: Any) -> None:
    secure_write_text(path, json.dumps(value, indent=2))


def secure_read_json(
    path: str | Path,
    *,
    missing: Any = None,
    fail_on_corrupt: bool = True,
) -> Any:
    """Read JSON while distinguishing a missing store from a corrupt store."""

    resolved = _resolved(path)
    _reject_symlink_components(resolved)
    if not resolved.exists():
        return missing
    try:
        if resolved.is_symlink() or not resolved.is_file():
            raise SecureStoreError(f"Unsafe configuration file {resolved}")
        os.chmod(resolved, CONFIG_FILE_MODE)
        with resolved.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError, TypeError) as error:
        if fail_on_corrupt:
            raise SecureStoreError(f"Invalid configuration file {resolved}") from error
        return missing


def enforce_config_permissions(root: str | Path | None = None) -> dict[str, int]:
    """Apply the centralized owner-only policy to every existing config entry."""

    resolved_root = _resolved(CONFIG_ROOT if root is None else root)
    ensure_config_directory(resolved_root)
    secured_files = 0
    secured_directories = 0
    try:
        for current_root, directories, files in os.walk(
            resolved_root,
            topdown=True,
            followlinks=False,
        ):
            current_path = Path(current_root)
            if current_path.is_symlink():
                raise SecureStoreError(f"Unsafe configuration link {current_path}")
            os.chmod(current_path, CONFIG_DIRECTORY_MODE)
            secured_directories += 1
            for name in directories:
                if (current_path / name).is_symlink():
                    raise SecureStoreError(
                        f"Unsafe configuration link {current_path / name}"
                    )
            for name in files:
                file_path = current_path / name
                if file_path.is_symlink():
                    raise SecureStoreError(f"Unsafe configuration link {file_path}")
                if not file_path.is_file():
                    continue
                os.chmod(file_path, CONFIG_FILE_MODE)
                secured_files += 1
    except SecureStoreError:
        raise
    except OSError as error:
        raise SecureStoreError(
            f"Unable to enforce configuration permissions under {resolved_root}"
        ) from error
    return {"files": secured_files, "directories": secured_directories}
