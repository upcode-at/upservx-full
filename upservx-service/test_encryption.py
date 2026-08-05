#!/usr/bin/env python3
"""
Test script for encryption functionality.
Run this to verify that encryption keys are properly generated and passwords can be encrypted/decrypted.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from encryption import get_encryption_manager, EncryptionManager
from config_manager import get_config_manager

def test_encryption():
    """Test encryption and decryption of passwords."""
    print("=" * 60)
    print("ENCRYPTION TEST")
    print("=" * 60)
    
    # Test 1: Ensure key exists
    print("\n1. Testing key generation...")
    try:
        EncryptionManager.ensure_key_exists()
        print("   ✓ Encryption key exists at /etc/upservx/encryption.key")
    except Exception as e:
        print(f"   ✗ Failed to ensure key exists: {e}")
        return False
    
    # Test 2: Get encryption manager
    print("\n2. Getting encryption manager...")
    try:
        encryption = get_encryption_manager()
        print("   ✓ Encryption manager initialized")
    except Exception as e:
        print(f"   ✗ Failed to get encryption manager: {e}")
        return False
    
    # Test 3: Encrypt a test password
    print("\n3. Testing password encryption...")
    test_password = "MySecureP@ssw0rd123!"
    try:
        encrypted = encryption.encrypt(test_password)
        print("   ✓ Password encrypted successfully")
    except Exception as e:
        print(f"   ✗ Failed to encrypt password: {e}")
        return False
    
    # Test 4: Decrypt the password
    print("\n4. Testing password decryption...")
    try:
        decrypted = encryption.decrypt(encrypted)
        if decrypted == test_password:
            print("   ✓ Password decrypted correctly - matches original")
        else:
            print("   ✗ Decrypted password does not match original")
            return False
    except Exception as e:
        print(f"   ✗ Failed to decrypt password: {e}")
        return False
    
    # Test 5: Test with config manager
    print("\n5. Testing config manager integration...")
    try:
        config = get_config_manager()
        
        # Add test server with password
        test_server = {
            'name': 'Test Backup Server',
            'type': 'remote',
            'host': '192.168.1.100',
            'port': 22,
            'remote_path': '/backups',
            'auth_type': 'password',
            'username': 'backup_user',
            'password': 'TestPassword123!'
        }
        
        print("   Adding test server with a test credential")
        created_server = config.add_backup_server(test_server)
        server_id = created_server['id']
        print(f"   ✓ Server created with ID: {server_id}")
        
        # Check that password is encrypted in storage
        if created_server.get('password_encrypted'):
            print("   ✓ Password marked as encrypted")
        else:
            print("   ✗ Password not marked as encrypted")
            return False
        
        # Retrieve server and check password is decrypted
        retrieved_server = config.get_backup_server(server_id, include_secret=True)
        if retrieved_server['password'] == 'TestPassword123!':
            print("   ✓ Retrieved password matches original (decryption works)")
        else:
            print("   ✗ Retrieved password does not match")
            return False
        
        # Check list doesn't expose passwords
        servers = config.get_backup_servers()
        matching_server = next((s for s in servers if s['id'] == server_id), None)
        if matching_server and matching_server['password'] is None:
            print("   ✓ Password hidden in list response (security)")
        else:
            print("   ✗ Password exposed in list response")
            return False
        
        # Clean up
        config.delete_backup_server(server_id)
        print("   ✓ Test server deleted")
        
    except Exception as e:
        print(f"   ✗ Config manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_encryption()
    sys.exit(0 if success else 1)
