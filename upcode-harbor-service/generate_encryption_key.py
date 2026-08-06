#!/usr/bin/env python3
"""
Generate a valid encryption key for Upcode Harbor.
This script creates a new Fernet encryption key and saves it to /etc/upcode-harbor/encryption.key
"""

import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet
from lib.secure_store import ensure_config_directory, secure_write_bytes

KEY_FILE = "/etc/upcode-harbor/encryption.key"
KEY_DIR = "/etc/upcode-harbor"

def generate_key():
    """Generate and save a new encryption key."""
    print("=" * 60)
    print("Upcode Harbor Encryption Key Generator")
    print("=" * 60)
    
    # Ensure directory exists
    key_dir = Path(KEY_DIR)
    if not key_dir.exists():
        print(f"\nCreating directory: {KEY_DIR}")
        try:
            ensure_config_directory(KEY_DIR)
            print(f"✓ Directory created with permissions 0700")
        except PermissionError:
            print(f"✗ Permission denied. Please run with sudo:")
            print(f"  sudo python3 {sys.argv[0]}")
            sys.exit(1)
    
    # Check if key already exists
    key_path = Path(KEY_FILE)
    if key_path.exists():
        print(f"\n⚠️  WARNING: Key file already exists at {KEY_FILE}")
        response = input("Do you want to overwrite it? This will make old encrypted passwords unreadable! (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)
        print("\nBacking up old key...")
        backup_path = f"{KEY_FILE}.backup"
        os.rename(KEY_FILE, backup_path)
        print(f"✓ Old key backed up to: {backup_path}")
    
    # Generate new key
    print(f"\nGenerating new Fernet encryption key...")
    key = Fernet.generate_key()
    print(f"✓ Key generated: {len(key)} bytes")
    
    # Save key with restricted permissions
    print(f"\nSaving key to: {KEY_FILE}")
    try:
        secure_write_bytes(KEY_FILE, key)
        print(f"✓ Key saved successfully")
        print(f"✓ Permissions set to 0600 (owner read/write only)")
        
    except PermissionError:
        print(f"✗ Permission denied. Please run with sudo:")
        print(f"  sudo python3 {sys.argv[0]}")
        sys.exit(1)
    
    # Verify the key
    print(f"\nVerifying key...")
    try:
        with open(KEY_FILE, 'rb') as f:
            loaded_key = f.read()
        
        # Test if it's a valid Fernet key
        cipher = Fernet(loaded_key)
        test_text = "test"
        encrypted = cipher.encrypt(test_text.encode())
        decrypted = cipher.decrypt(encrypted).decode()
        
        if decrypted == test_text:
            print(f"✓ Key verification successful!")
            print(f"✓ Encryption/decryption test passed")
        else:
            print(f"✗ Key verification failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"✗ Key verification failed: {e}")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✓ Encryption key setup complete!")
    print("=" * 60)
    print(f"\nKey location: {KEY_FILE}")
    print(f"Key permissions: 0600")
    print("\nYou can now create backup servers with encrypted passwords.")
    print("\n⚠️  IMPORTANT: Backup this key file if you backup your configuration!")

if __name__ == "__main__":
    try:
        generate_key()
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
