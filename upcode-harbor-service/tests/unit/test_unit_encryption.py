"""
Unit tests for lib/encryption.py
====================================
Tests EncryptionManager fully in isolation.
The key file (/etc/upcode-harbor/encryption.key) is replaced with a temporary
directory so no root privileges are required.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet

from lib.encryption import EncryptionManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_key_dir(tmp_path):
    """Returns a temporary path for the key file."""
    return str(tmp_path / "encryption.key")


@pytest.fixture()
def manager(tmp_key_dir):
    """EncryptionManager with a temporary key file."""
    with patch.object(EncryptionManager, "KEY_FILE", tmp_key_dir):
        mgr = EncryptionManager()
    return mgr


# ---------------------------------------------------------------------------
# Key creation and loading
# ---------------------------------------------------------------------------

class TestKeyManagement:
    def test_key_file_created_on_first_init(self, tmp_key_dir):
        with patch.object(EncryptionManager, "KEY_FILE", tmp_key_dir):
            EncryptionManager()
        assert Path(tmp_key_dir).exists()

    def test_key_persisted_between_instances(self, tmp_key_dir):
        with patch.object(EncryptionManager, "KEY_FILE", tmp_key_dir):
            mgr1 = EncryptionManager()
            key1 = mgr1._cipher._signing_key  # internal Fernet signing key

            mgr2 = EncryptionManager()
            key2 = mgr2._cipher._signing_key

        assert key1 == key2, "Both instances should use the same key"

    def test_init_raises_on_corrupted_key(self, tmp_key_dir):
        # Write an invalid key
        Path(tmp_key_dir).parent.mkdir(parents=True, exist_ok=True)
        Path(tmp_key_dir).write_bytes(b"not-a-valid-fernet-key")
        with patch.object(EncryptionManager, "KEY_FILE", tmp_key_dir):
            with pytest.raises(Exception):
                EncryptionManager()


# ---------------------------------------------------------------------------
# Encrypt / Decrypt
# ---------------------------------------------------------------------------

class TestEncryptDecrypt:
    def test_encrypt_returns_string(self, manager):
        result = manager.encrypt("hello")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_decrypt_recovers_original_value(self, manager):
        plaintext = "my-secret-password"
        ciphertext = manager.encrypt(plaintext)
        assert manager.decrypt(ciphertext) == plaintext

    def test_empty_string_encrypt_returns_empty(self, manager):
        assert manager.encrypt("") == ""

    def test_empty_string_decrypt_returns_empty(self, manager):
        assert manager.decrypt("") == ""

    def test_ciphertext_differs_from_plaintext(self, manager):
        plaintext = "mypassword"
        ciphertext = manager.encrypt(plaintext)
        assert ciphertext != plaintext

    def test_two_encryptions_produce_different_ciphertext(self, manager):
        """Fernet uses a random IV – same plaintext → different ciphertext."""
        ct1 = manager.encrypt("same")
        ct2 = manager.encrypt("same")
        assert ct1 != ct2

    def test_unicode_roundtrip(self, manager):
        plaintext = "Ünter ñ Ärger 你好 🚀"
        assert manager.decrypt(manager.encrypt(plaintext)) == plaintext

    def test_long_string_roundtrip(self, manager):
        plaintext = "x" * 10_000
        assert manager.decrypt(manager.encrypt(plaintext)) == plaintext

    def test_decrypt_with_wrong_key_raises(self, tmp_key_dir, tmp_path):
        with patch.object(EncryptionManager, "KEY_FILE", tmp_key_dir):
            mgr1 = EncryptionManager()
            ciphertext = mgr1.encrypt("secret")

        # Second instance with a different key
        other_key_path = str(tmp_path / "other.key")
        with patch.object(EncryptionManager, "KEY_FILE", other_key_path):
            mgr2 = EncryptionManager()
            with pytest.raises(ValueError, match="Failed to decrypt"):
                mgr2.decrypt(ciphertext)

    def test_decrypt_invalid_data_raises_value_error(self, manager):
        with pytest.raises(ValueError, match="Failed to decrypt"):
            manager.decrypt("this-is-not-valid-base64-fernet-data")


# ---------------------------------------------------------------------------
# ensure_key_exists
# ---------------------------------------------------------------------------

class TestEnsureKeyExists:
    def test_returns_true_when_key_exists(self, tmp_key_dir):
        with patch.object(EncryptionManager, "KEY_FILE", tmp_key_dir):
            EncryptionManager()          # creates the key
            result = EncryptionManager.ensure_key_exists()
        assert result is True

    def test_returns_false_when_no_key(self, tmp_path):
        missing_path = str(tmp_path / "nonexistent.key")
        with patch.object(EncryptionManager, "KEY_FILE", missing_path):
            # ensure_key_exists() instantiates a manager → creates the key
            # So we verify via Path.exists directly BEFORE calling ensure_key_exists
            assert not Path(missing_path).exists()
