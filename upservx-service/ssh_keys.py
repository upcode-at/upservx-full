"""
SSH Key management utilities for backup servers.
"""

import os
import stat
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, ed25519
import logging

logger = logging.getLogger(__name__)

SSH_KEY_DIR = "./ssh_keys"
AUTHORIZED_KEYS_DIR = "./authorized_keys"


class SSHKeyManager:
    """Manage SSH keys for backup authentication."""
    
    def __init__(self):
        self.ensure_directories()
    
    def ensure_directories(self):
        """Ensure SSH key directories exist with proper permissions."""
        for directory in [SSH_KEY_DIR, AUTHORIZED_KEYS_DIR]:
            os.makedirs(directory, exist_ok=True)
            os.chmod(directory, 0o700)
    
    def generate_ssh_key_pair(self, 
                            key_name: str, 
                            key_type: str = "rsa", 
                            key_size: int = 4096,
                            passphrase: Optional[str] = None) -> Dict[str, str]:
        """
        Generate a new SSH key pair.
        
        Args:
            key_name: Name for the key pair
            key_type: Type of key (rsa, ed25519)
            key_size: Key size for RSA keys
            passphrase: Optional passphrase for private key
            
        Returns:
            Dictionary containing private key, public key, and paths
        """
        try:
            private_key_path = os.path.join(SSH_KEY_DIR, f"{key_name}")
            public_key_path = f"{private_key_path}.pub"
            
            if key_type.lower() == "rsa":
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=key_size
                )
            elif key_type.lower() == "ed25519":
                private_key = ed25519.Ed25519PrivateKey.generate()
            else:
                raise ValueError(f"Unsupported key type: {key_type}")
            
            # Serialize private key
            encryption_algorithm = serialization.NoEncryption()
            if passphrase:
                encryption_algorithm = serialization.BestAvailableEncryption(
                    passphrase.encode()
                )
            
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.OpenSSH,
                encryption_algorithm=encryption_algorithm
            )
            
            # Serialize public key
            public_key = private_key.public_key()
            public_ssh = public_key.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            )
            
            # Write private key
            with open(private_key_path, 'wb') as f:
                f.write(private_pem)
            os.chmod(private_key_path, 0o600)
            
            # Write public key
            public_key_content = f"{public_ssh.decode()} {key_name}@upservx"
            with open(public_key_path, 'w') as f:
                f.write(public_key_content)
            os.chmod(public_key_path, 0o644)
            
            return {
                'private_key': private_pem.decode(),
                'public_key': public_key_content,
                'private_key_path': private_key_path,
                'public_key_path': public_key_path,
                'fingerprint': self.get_key_fingerprint(public_key_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate SSH key pair: {e}")
            raise
    
    def store_ssh_key(self, 
                     key_name: str, 
                     private_key_content: str,
                     passphrase: Optional[str] = None) -> Dict[str, str]:
        """
        Store an existing SSH private key.
        
        Args:
            key_name: Name for the stored key
            private_key_content: Private key content
            passphrase: Optional passphrase for the key
            
        Returns:
            Dictionary with key information
        """
        try:
            private_key_path = os.path.join(SSH_KEY_DIR, f"{key_name}")
            
            # Validate the key by trying to load it
            try:
                key_bytes = private_key_content.encode()
                passphrase_bytes = passphrase.encode() if passphrase else None
                
                serialization.load_pem_private_key(
                    key_bytes, 
                    password=passphrase_bytes
                )
            except Exception as e:
                raise ValueError(f"Invalid private key: {e}")
            
            # Store the key
            with open(private_key_path, 'w') as f:
                f.write(private_key_content)
            os.chmod(private_key_path, 0o600)
            
            # Generate public key if possible
            public_key_path = f"{private_key_path}.pub"
            try:
                result = subprocess.run([
                    'ssh-keygen', '-y', '-f', private_key_path
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    public_key_content = f"{result.stdout.strip()} {key_name}@upservx"
                    with open(public_key_path, 'w') as f:
                        f.write(public_key_content)
                    os.chmod(public_key_path, 0o644)
                else:
                    public_key_content = "Could not extract public key"
            except Exception:
                public_key_content = "Could not extract public key"
            
            return {
                'private_key_path': private_key_path,
                'public_key_path': public_key_path if os.path.exists(public_key_path) else None,
                'public_key': public_key_content,
                'fingerprint': self.get_key_fingerprint(public_key_path) if os.path.exists(public_key_path) else None
            }
            
        except Exception as e:
            logger.error(f"Failed to store SSH key: {e}")
            raise
    
    def get_key_fingerprint(self, public_key_path: str) -> Optional[str]:
        """Get fingerprint of an SSH public key."""
        try:
            result = subprocess.run([
                'ssh-keygen', '-l', '-f', public_key_path
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return result.stdout.strip().split()[1]
            return None
        except Exception:
            return None
    
    def list_ssh_keys(self) -> List[Dict[str, str]]:
        """List all stored SSH keys."""
        keys = []
        try:
            for file_path in Path(SSH_KEY_DIR).iterdir():
                if file_path.is_file() and not file_path.name.endswith('.pub'):
                    key_name = file_path.name
                    public_key_path = f"{file_path}.pub"
                    
                    key_info = {
                        'name': key_name,
                        'private_key_path': str(file_path),
                        'public_key_path': public_key_path if os.path.exists(public_key_path) else None,
                        'fingerprint': self.get_key_fingerprint(public_key_path) if os.path.exists(public_key_path) else None,
                        'created': os.path.getctime(file_path)
                    }
                    keys.append(key_info)
        except Exception as e:
            logger.error(f"Failed to list SSH keys: {e}")
        
        return keys
    
    def delete_ssh_key(self, key_name: str) -> bool:
        """Delete an SSH key pair."""
        try:
            private_key_path = os.path.join(SSH_KEY_DIR, key_name)
            public_key_path = f"{private_key_path}.pub"
            
            deleted = False
            for path in [private_key_path, public_key_path]:
                if os.path.exists(path):
                    os.remove(path)
                    deleted = True
            
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete SSH key {key_name}: {e}")
            return False
    
    def get_ssh_key(self, key_name: str) -> Optional[Dict[str, str]]:
        """Get SSH key information by name."""
        try:
            private_key_path = os.path.join(SSH_KEY_DIR, key_name)
            public_key_path = f"{private_key_path}.pub"
            
            if not os.path.exists(private_key_path):
                return None
            
            result = {
                'name': key_name,
                'private_key_path': private_key_path,
                'public_key_path': public_key_path if os.path.exists(public_key_path) else None,
                'fingerprint': self.get_key_fingerprint(public_key_path) if os.path.exists(public_key_path) else None
            }
            
            # Read public key content if available
            if os.path.exists(public_key_path):
                with open(public_key_path, 'r') as f:
                    result['public_key'] = f.read().strip()
            
            return result
        except Exception as e:
            logger.error(f"Failed to get SSH key {key_name}: {e}")
            return None
    
    def test_ssh_connection(self, 
                          host: str, 
                          username: str, 
                          key_path: str, 
                          port: int = 22,
                          passphrase: Optional[str] = None) -> Tuple[bool, str]:
        """
        Test SSH connection with a private key.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            import paramiko
            
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Load private key
            try:
                if passphrase:
                    key = paramiko.RSAKey.from_private_key_file(key_path, password=passphrase)
                else:
                    # Try different key types
                    key = None
                    for key_class in [paramiko.RSAKey, paramiko.DSSKey, paramiko.ECDSAKey, paramiko.Ed25519Key]:
                        try:
                            key = key_class.from_private_key_file(key_path)
                            break
                        except Exception:
                            continue
                    
                    if not key:
                        return False, "Could not load private key"
            except Exception as e:
                return False, f"Key loading error: {str(e)}"
            
            # Test connection
            client.connect(
                hostname=host,
                port=port,
                username=username,
                pkey=key,
                timeout=10,
                look_for_keys=False
            )
            
            # Execute a simple command to verify connection
            stdin, stdout, stderr = client.exec_command('echo "test"')
            result = stdout.read().decode().strip()
            
            client.close()
            
            if result == "test":
                return True, "Connection successful"
            else:
                return False, "Connection failed - could not execute commands"
                
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def setup_authorized_keys(self, 
                            username: str, 
                            public_keys: List[str]) -> bool:
        """Setup authorized_keys file for a user."""
        try:
            auth_keys_path = os.path.join(AUTHORIZED_KEYS_DIR, f"{username}_authorized_keys")
            
            with open(auth_keys_path, 'w') as f:
                for key in public_keys:
                    f.write(f"{key}\n")
            
            os.chmod(auth_keys_path, 0o600)
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup authorized keys for {username}: {e}")
            return False


# Global SSH key manager instance
ssh_key_manager = SSHKeyManager()