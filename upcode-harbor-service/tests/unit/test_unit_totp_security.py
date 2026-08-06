"""Tests for encrypted TOTP state and password-free first-factor tokens."""

import hashlib
import json
import time

import pytest

from lib import totp
from lib.encryption import EncryptionManager
from lib.secure_store import SecureStoreError, secure_write_json


@pytest.fixture()
def totp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(totp, "_2FA_FILE", str(tmp_path / "2fa.json"))
    monkeypatch.setattr(totp, "_SETUP_FILE", str(tmp_path / "2fa_setup.json"))
    monkeypatch.setattr(
        totp, "_LOGIN_TOKENS_FILE", str(tmp_path / "login_tokens.json")
    )
    monkeypatch.setattr(
        EncryptionManager, "KEY_FILE", str(tmp_path / "encryption.key")
    )
    manager = EncryptionManager()
    monkeypatch.setattr(totp, "get_encryption_manager", lambda: manager)
    return tmp_path, manager


def test_login_token_contains_no_linux_password_and_is_one_time(
    totp_store, monkeypatch
):
    tmp_path, _ = totp_store
    token = totp.create_login_token("alice")
    raw = (tmp_path / "login_tokens.json").read_text()
    persisted = json.loads(raw)

    assert token not in raw
    assert "password" not in raw
    assert "enc_password" not in raw
    assert hashlib.sha256(token.encode()).hexdigest() in persisted
    assert persisted[next(iter(persisted))]["username"] == "alice"

    monkeypatch.setattr(totp, "verify_code", lambda username, code: True)
    assert totp.consume_login_token(token, "123456") == "alice"
    assert totp.consume_login_token(token, "123456") is None


def test_legacy_login_token_migration_drops_passwords_and_hashes_tokens(totp_store):
    tmp_path, _ = totp_store
    path = tmp_path / "login_tokens.json"
    secure_write_json(
        path,
        {
            "plaintext-token": {
                "username": "alice",
                "enc_password": "encrypted-linux-password",
                "expires": time.time() + 60,
            }
        },
    )

    totp.migrate_login_token_store()

    raw = path.read_text()
    migrated = json.loads(raw)
    assert "password" not in raw
    assert "plaintext-token" not in raw
    assert hashlib.sha256(b"plaintext-token").hexdigest() in migrated


def test_pending_totp_secret_is_encrypted_at_rest(totp_store, monkeypatch):
    tmp_path, manager = totp_store
    known_secret = "JBSWY3DPEHPK3PXP"
    monkeypatch.setattr(totp.pyotp, "random_base32", lambda: known_secret)

    token, uri = totp.create_pending_setup("alice")
    persisted = json.loads((tmp_path / "2fa_setup.json").read_text())
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    encrypted = persisted[token_hash]["encrypted_secret"]

    assert known_secret not in (tmp_path / "2fa_setup.json").read_text()
    assert token not in persisted
    assert manager.decrypt(encrypted) == known_secret
    assert known_secret in uri


def test_corrupt_totp_state_does_not_look_like_disabled_2fa(totp_store):
    tmp_path, _ = totp_store
    (tmp_path / "2fa.json").write_text("not-json")

    with pytest.raises(SecureStoreError):
        totp.is_enabled("alice")


def test_wrong_codes_are_limited_to_five_attempts(totp_store, monkeypatch):
    tmp_path, _ = totp_store
    token = totp.create_login_token("alice")
    monkeypatch.setattr(totp, "verify_code", lambda username, code: False)

    for _ in range(5):
        assert totp.consume_login_token(token, "wrong") is None

    assert json.loads((tmp_path / "login_tokens.json").read_text()) == {}
