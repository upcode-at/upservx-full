"""
Encryption module for secure password storage.
Uses Fernet (symmetric encryption) with a device-specific key.
"""
import os
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Optional

from lib.secure_store import secure_write_bytes

class EncryptionManager:
    """Manages encryption and decryption of sensitive data using a device-specific key."""
    
    KEY_FILE = "/etc/upcode-harbor/encryption.key"
    
    def __init__(self):
        """Initialize the encryption manager and load or generate the key."""
        self._cipher = None
        self._load_or_generate_key()
    
    def _load_or_generate_key(self):
        """Load existing key or generate a new one if it doesn't exist."""
        key_path = Path(self.KEY_FILE)
        
        if key_path.exists():
            try:
                if key_path.is_symlink() or not key_path.is_file():
                    raise RuntimeError("Unsafe encryption key path")
                with open(key_path, 'rb') as f:
                    key = f.read().strip()
                os.chmod(key_path, 0o600)
                self._cipher = Fernet(key)
            except Exception as error:
                raise RuntimeError("Unable to load the encryption key") from error
        else:
            self._generate_and_save_key()
    
    def _generate_and_save_key(self):
        """Generate a new encryption key and save it securely."""
        key = Fernet.generate_key()
        secure_write_bytes(self.KEY_FILE, key)
        self._cipher = Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""
        
        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as error:
            raise RuntimeError("Failed to encrypt sensitive data") from error
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            encrypted_text: The base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
        """
        if not encrypted_text:
            return ""
        
        try:
            decrypted_bytes = self._cipher.decrypt(encrypted_text.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception as error:
            raise ValueError("Failed to decrypt data") from error
    
    @staticmethod
    def ensure_key_exists():
        """Ensure the encryption key exists. Called during installation."""
        manager = EncryptionManager()
        return Path(manager.KEY_FILE).exists()

_encryption_manager: Optional[EncryptionManager] = None

def get_encryption_manager() -> EncryptionManager:
    """Get or create the global encryption manager instance."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager
