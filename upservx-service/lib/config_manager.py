"""
Configuration management for /etc/upservx settings.
Handles persistent storage of backup servers and other system configurations.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from lib.encryption import get_encryption_manager
from lib.file_lock import InterProcessFileLock
from lib.secure_store import (
    SecureStoreError,
    ensure_config_directory,
    secure_read_json,
    secure_write_json,
    secure_write_text,
)

CONFIG_DIR = os.getenv("UPSERVX_CONFIG_DIR", "/etc/upservx")
BACKUP_DIR = os.path.join(CONFIG_DIR, "backup")
BACKUP_SERVERS_FILE = os.path.join(BACKUP_DIR, "backup_servers.json")
STATE_DIR = os.getenv("UPSERVX_STATE_DIR", "/var/lib/upservx")
SSH_KEYS_DIR = os.getenv("UPSERVX_SSH_KEY_DIR", os.path.join(STATE_DIR, "ssh_keys"))

class ConfigManager:
    """Manage /etc/upservx configuration files."""

    def __init__(self):
        """Initialize config manager and ensure directories exist."""
        self._ensure_directories()
        self._migrate_backup_files()

    def _ensure_directories(self):
        """Create necessary directories if they don't exist."""
        try:
            ensure_config_directory(CONFIG_DIR)
            ensure_config_directory(SSH_KEYS_DIR)
            ensure_config_directory(BACKUP_DIR)
        except Exception as e:
            print(f"Warning: Could not create config directories: {e}")

    def _migrate_backup_files(self):
        """Migrate old backup_servers.json from root config dir to backup subdir."""
        old_backup_servers = os.path.join(CONFIG_DIR, "backup_servers.json")
        try:
            with InterProcessFileLock(f"{BACKUP_SERVERS_FILE}.lock"):
                if (
                    old_backup_servers == BACKUP_SERVERS_FILE
                    or not os.path.exists(old_backup_servers)
                    or os.path.exists(BACKUP_SERVERS_FILE)
                ):
                    return
                shutil.move(old_backup_servers, BACKUP_SERVERS_FILE)
                os.chmod(BACKUP_SERVERS_FILE, 0o600)
                print(f"Migrated backup_servers.json to {BACKUP_SERVERS_FILE}")
        except Exception as e:
            print(f"Warning: Could not migrate backup_servers.json: {e}")
    
    def _read_json_file(self, filepath: str, default: Any = None) -> Any:
        """Read and parse JSON file."""
        try:
            return secure_read_json(
                filepath,
                missing=default if default is not None else {},
            )
        except SecureStoreError as error:
            raise RuntimeError("Configuration file is invalid") from error
    
    def _write_json_file(self, filepath: str, data: Any) -> bool:
        """Write data to JSON file."""
        try:
            secure_write_json(filepath, data)
            return True
        except Exception as e:
            print(f"Error writing {filepath}: {e}")
            return False
    
    # Backup Servers

    def _backup_store(self):
        """Return the canonical SQLite store for compatibility callers."""
        store = getattr(self, "_backup_store_instance", None)
        if store is None:
            from lib.backup_db import BackupDatabase

            store = BackupDatabase(
                os.path.join(BACKUP_DIR, "backup.db"),
                BACKUP_SERVERS_FILE,
            )
            self._backup_store_instance = store
        return store

    def get_backup_servers(self) -> List[Dict[str, Any]]:
        """Compatibility wrapper around the canonical SQLite store."""
        return self._backup_store().get_backup_servers()

    def get_backup_server(
        self,
        server_id: int,
        *,
        include_secret: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Get a server and decrypt credentials only for internal callers."""
        server = self._backup_store().get_backup_server(
            server_id,
            include_secrets=include_secret,
        )
        if not server or not include_secret:
            return server
        if server.get("password_encrypted"):
            server["password"] = get_encryption_manager().decrypt(
                server["password_encrypted"]
            )
        if server.get("ssh_key_passphrase_encrypted"):
            server["ssh_key_passphrase"] = get_encryption_manager().decrypt(
                server["ssh_key_passphrase_encrypted"]
            )
        return server
    
    def add_backup_server(self, server_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a backup server to SQLite; JSON is migration input only."""
        server_data = server_data.copy()
        password = server_data.pop("password", None)
        passphrase = server_data.pop("ssh_key_passphrase", None)
        if password:
            server_data["password_encrypted"] = get_encryption_manager().encrypt(password)
        if passphrase:
            server_data["ssh_key_passphrase_encrypted"] = (
                get_encryption_manager().encrypt(passphrase)
            )
        server_id = self._backup_store().create_backup_server(server_data)
        return self._backup_store().get_backup_server(server_id)
    
    def update_backup_server(self, server_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing SQLite backup server."""
        updates = updates.copy()
        if "password" in updates:
            password = updates.pop("password")
            updates["password_encrypted"] = get_encryption_manager().encrypt(password)
        if "ssh_key_passphrase" in updates:
            passphrase = updates.pop("ssh_key_passphrase")
            updates["ssh_key_passphrase_encrypted"] = (
                get_encryption_manager().encrypt(passphrase)
            )
        if not self._backup_store().update_backup_server(server_id, updates):
            return None
        return self._backup_store().get_backup_server(server_id)
    
    def delete_backup_server(self, server_id: int) -> bool:
        """Delete an unused backup server from SQLite."""
        return self._backup_store().delete_backup_server(server_id)
    
    # SSH Key Management
    
    def save_ssh_key(self, key_name: str, key_content: str) -> str:
        """Save SSH private key to secure directory."""
        if not key_name or os.path.basename(key_name) != key_name:
            raise ValueError("Invalid SSH key name")
        key_path = os.path.join(SSH_KEYS_DIR, key_name)
        
        try:
            secure_write_text(key_path, key_content)
            return key_path
        except Exception as e:
            raise Exception(f"Failed to save SSH key: {e}")
    
    def get_ssh_key_path(self, key_name: str) -> Optional[str]:
        """Get path to SSH key if it exists."""
        key_path = os.path.join(SSH_KEYS_DIR, key_name)
        if os.path.exists(key_path):
            return key_path
        return None
    
    def delete_ssh_key(self, key_name: str) -> bool:
        """Delete SSH key file."""
        key_path = os.path.join(SSH_KEYS_DIR, key_name)
        try:
            if os.path.exists(key_path):
                os.remove(key_path)
                return True
        except Exception as e:
            print(f"Error deleting SSH key {key_name}: {e}")
        return False
    
    def list_ssh_keys(self) -> List[str]:
        """List all stored SSH key names."""
        try:
            if os.path.exists(SSH_KEYS_DIR):
                return [f for f in os.listdir(SSH_KEYS_DIR) if os.path.isfile(os.path.join(SSH_KEYS_DIR, f))]
        except Exception as e:
            print(f"Error listing SSH keys: {e}")
        return []
    
    # General Settings
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a general setting value."""
        settings_file = os.path.join(CONFIG_DIR, "settings.json")
        data = self._read_json_file(settings_file, {})
        return data.get(key, default)
    
    def set_setting(self, key: str, value: Any) -> bool:
        """Set a general setting value."""
        settings_file = os.path.join(CONFIG_DIR, "settings.json")
        with InterProcessFileLock(f"{settings_file}.lock"):
            data = self._read_json_file(settings_file, {})
            data[key] = value
            return self._write_json_file(settings_file, data)
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all general settings."""
        settings_file = os.path.join(CONFIG_DIR, "settings.json")
        return self._read_json_file(settings_file, {})

_config_manager = None

def get_config_manager() -> ConfigManager:
    """Get or create config manager singleton."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
