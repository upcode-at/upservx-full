"""
Configuration management for /etc/upservx settings.
Handles persistent storage of backup servers and other system configurations.
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from lib.encryption import get_encryption_manager

CONFIG_DIR = "/etc/upservx"
BACKUP_SERVERS_FILE = os.path.join(CONFIG_DIR, "backup_servers.json")
SSH_KEYS_DIR = os.path.join(CONFIG_DIR, "ssh_keys")

class ConfigManager:
    """Manage /etc/upservx configuration files."""
    
    def __init__(self):
        """Initialize config manager and ensure directories exist."""
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create necessary directories if they don't exist."""
        try:
            os.makedirs(CONFIG_DIR, mode=0o755, exist_ok=True)
            os.makedirs(SSH_KEYS_DIR, mode=0o700, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create config directories: {e}")
    
    def _read_json_file(self, filepath: str, default: Any = None) -> Any:
        """Read and parse JSON file."""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
        return default if default is not None else {}
    
    def _write_json_file(self, filepath: str, data: Any) -> bool:
        """Write data to JSON file."""
        try:
            temp_file = f"{filepath}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Atomic rename
            shutil.move(temp_file, filepath)
            os.chmod(filepath, 0o644)
            return True
        except Exception as e:
            print(f"Error writing {filepath}: {e}")
            return False
    
    # Backup Servers
    
    def get_backup_servers(self) -> List[Dict[str, Any]]:
        """Get all configured backup servers."""
        data = self._read_json_file(BACKUP_SERVERS_FILE, {"servers": []})
        servers = data.get("servers", [])
        
        # Return servers without exposing encrypted passwords
        return [{**server, 'password': None} if server.get('password_encrypted') else server 
                for server in servers]
    
    def get_backup_server(self, server_id: int) -> Optional[Dict[str, Any]]:
        """Get specific backup server by ID with decrypted password."""
        # Read directly from file to get encrypted password
        data = self._read_json_file(BACKUP_SERVERS_FILE, {"servers": []})
        servers = data.get("servers", [])
        
        for server in servers:
            if server.get("id") == server_id:
                # Decrypt password if encrypted
                if server.get("password_encrypted") and server.get("password"):
                    print(f"[CONFIG] Decrypting password for server {server_id}...")
                    try:
                        encryption = get_encryption_manager()
                        server_copy = server.copy()
                        encrypted_password = server["password"]
                        print(f"[CONFIG] Encrypted password: {encrypted_password[:20]}...")
                        decrypted = encryption.decrypt(encrypted_password)
                        server_copy["password"] = decrypted
                        print(f"[CONFIG] Password decrypted successfully")
                        return server_copy
                    except Exception as e:
                        print(f"[CONFIG] ERROR decrypting password: {e}")
                        raise
                return server
        return None
    
    def add_backup_server(self, server_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add new backup server configuration."""
        print("[CONFIG] add_backup_server called")
        print(f"[CONFIG] Input server_data: {server_data}")
        
        servers = self.get_backup_servers()
        print(f"[CONFIG] Current servers count: {len(servers)}")
        
        max_id = max([s.get("id", 0) for s in servers], default=0)
        server_data["id"] = max_id + 1
        server_data["created"] = datetime.now().isoformat()
        server_data["status"] = "active"
        print(f"[CONFIG] Generated ID: {server_data['id']}")
        
        if "password" in server_data and server_data["password"]:
            print("[CONFIG] Encrypting password...")
            try:
                encryption = get_encryption_manager()
                print("[CONFIG] Encryption manager obtained")
                encrypted_password = encryption.encrypt(server_data["password"])
                print(f"[CONFIG] Password encrypted: {encrypted_password[:20]}...")
                server_data["password"] = encrypted_password
                server_data["password_encrypted"] = True
            except Exception as e:
                print(f"[CONFIG] ERROR encrypting password: {e}")
                import traceback
                traceback.print_exc()
                raise
        
        servers.append(server_data)
        print("[CONFIG] Server appended to list")
        
        if self._write_json_file(BACKUP_SERVERS_FILE, {"servers": servers}):
            return server_data
        else:
            raise Exception("Failed to save backup server configuration")
    
    def update_backup_server(self, server_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update existing backup server."""
        servers = self.get_backup_servers()
        
        if "password" in updates and updates["password"]:
            encryption = get_encryption_manager()
            updates["password"] = encryption.encrypt(updates["password"])
            updates["password_encrypted"] = True
        
        for i, server in enumerate(servers):
            if server.get("id") == server_id:
                server.update(updates)
                server["updated"] = datetime.now().isoformat()
                servers[i] = server
                
                if self._write_json_file(BACKUP_SERVERS_FILE, {"servers": servers}):
                    return server
                else:
                    raise Exception("Failed to update backup server configuration")
        
        return None
    
    def delete_backup_server(self, server_id: int) -> bool:
        """Delete backup server configuration."""
        servers = self.get_backup_servers()
        original_count = len(servers)
        
        servers = [s for s in servers if s.get("id") != server_id]
        
        if len(servers) < original_count:
            return self._write_json_file(BACKUP_SERVERS_FILE, {"servers": servers})
        
        return False
    
    # SSH Key Management
    
    def save_ssh_key(self, key_name: str, key_content: str) -> str:
        """Save SSH private key to secure directory."""
        key_path = os.path.join(SSH_KEYS_DIR, key_name)
        
        try:
            with open(key_path, 'w') as f:
                f.write(key_content)
            
            # Set restrictive permissions
            os.chmod(key_path, 0o600)
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
