"""
Encryption module for secure password storage.
Uses Fernet (symmetric encryption) with a device-specific key.
"""
import os
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Optional


class EncryptionManager:
    """Manages encryption and decryption of sensitive data using a device-specific key."""
    
    KEY_FILE = "/etc/upservx/encryption.key"
    
    def __init__(self):
        """Initialize the encryption manager and load or generate the key."""
        self._cipher = None
        self._load_or_generate_key()
    
    def _load_or_generate_key(self):
        """Load existing key or generate a new one if it doesn't exist."""
        key_path = Path(self.KEY_FILE)
        print(f"[ENCRYPTION] Checking for key at: {self.KEY_FILE}")
        
        if key_path.exists():
            # Load existing key
            print("[ENCRYPTION] Loading existing key...")
            try:
                with open(key_path, 'rb') as f:
                    key = f.read().strip()  # Remove any whitespace/newlines
                print(f"[ENCRYPTION] Key length: {len(key)} bytes")
                self._cipher = Fernet(key)
                print("[ENCRYPTION] Key loaded successfully")
            except Exception as e:
                print(f"[ENCRYPTION] ERROR loading key: {e}")
                print(f"[ENCRYPTION] Key content (first 20 chars): {key[:20] if key else 'empty'}")
                raise
        else:
            # Generate new key
            print("[ENCRYPTION] Key not found, generating new key...")
            self._generate_and_save_key()
    
    def _generate_and_save_key(self):
        """Generate a new encryption key and save it securely."""
        # Ensure directory exists
        key_dir = Path(self.KEY_FILE).parent
        key_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(key_dir, 0o755)
        
        # Generate new key
        key = Fernet.generate_key()
        
        # Save key with restricted permissions
        temp_file = f"{self.KEY_FILE}.tmp"
        with open(temp_file, 'wb') as f:
            f.write(key)
        
        # Set restrictive permissions (only root can read)
        os.chmod(temp_file, 0o600)
        
        # Atomic move
        os.rename(temp_file, self.KEY_FILE)
        
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
        
        print(f"[ENCRYPTION] Encrypting plaintext of length: {len(plaintext)}")
        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode('utf-8'))
            result = encrypted_bytes.decode('utf-8')
            print(f"[ENCRYPTION] Encryption successful, result length: {len(result)}")
            return result
        except Exception as e:
            print(f"[ENCRYPTION] ERROR during encryption: {e}")
            raise
    
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
        except Exception as e:
            raise ValueError(f"Failed to decrypt data: {str(e)}")
    
    @staticmethod
    def ensure_key_exists():
        """Ensure the encryption key exists. Called during installation."""
        manager = EncryptionManager()
        return Path(manager.KEY_FILE).exists()


# Global instance
_encryption_manager: Optional[EncryptionManager] = None


def get_encryption_manager() -> EncryptionManager:
    """Get or create the global encryption manager instance."""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager
