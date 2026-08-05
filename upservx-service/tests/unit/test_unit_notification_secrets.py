"""Tests for encrypted notification credentials and safe API views."""

import json

import pytest

from handlers import notifications
from lib.encryption import EncryptionManager
from lib.models import NotificationConfig


@pytest.fixture()
def notification_store(tmp_path, monkeypatch):
    path = tmp_path / "notifications.json"
    monkeypatch.setattr(notifications, "NOTIFICATIONS_FILE", str(path))
    monkeypatch.setattr(
        EncryptionManager, "KEY_FILE", str(tmp_path / "encryption.key")
    )
    manager = EncryptionManager()
    monkeypatch.setattr(notifications, "get_encryption_manager", lambda: manager)
    return path


def test_notification_credentials_are_encrypted_and_hidden_by_default(
    notification_store,
):
    config = NotificationConfig(
        email={"enabled": True, "smtp_password": "smtp-secret"},
        webhook={"enabled": True, "url": "https://example.invalid", "secret": "hook-secret"},
    )

    notifications.save_notifications(config)
    raw = notification_store.read_text()

    assert "smtp-secret" not in raw
    assert "hook-secret" not in raw
    assert "smtp_password_encrypted" in raw
    assert "secret_encrypted" in raw
    safe = notifications.load_notifications()
    assert safe.email.smtp_password == ""
    assert safe.webhook.secret == ""
    internal = notifications.load_notifications(include_secrets=True)
    assert internal.email.smtp_password == "smtp-secret"
    assert internal.webhook.secret == "hook-secret"


def test_blank_updates_preserve_existing_encrypted_credentials(notification_store):
    notifications.save_notifications(
        NotificationConfig(
            email={"smtp_password": "smtp-secret"},
            webhook={"secret": "hook-secret"},
        )
    )
    before = json.loads(notification_store.read_text())

    notifications.save_notifications(NotificationConfig())
    after = json.loads(notification_store.read_text())

    assert after["email"]["smtp_password_encrypted"] == before["email"]["smtp_password_encrypted"]
    assert after["webhook"]["secret_encrypted"] == before["webhook"]["secret_encrypted"]


def test_legacy_plaintext_is_migrated_before_any_safe_view_is_returned(
    notification_store,
):
    notification_store.write_text(
        json.dumps(
            {
                "email": {"smtp_password": "legacy-smtp"},
                "webhook": {"secret": "legacy-hook"},
            }
        )
    )

    safe = notifications.load_notifications()

    assert safe.email.smtp_password == ""
    assert safe.webhook.secret == ""
    raw = notification_store.read_text()
    assert "legacy-smtp" not in raw
    assert "legacy-hook" not in raw


def test_encryption_failure_does_not_write_plaintext(notification_store, monkeypatch):
    class BrokenEncryption:
        def encrypt(self, _value):
            raise RuntimeError("encryption unavailable")

    monkeypatch.setattr(
        notifications, "get_encryption_manager", lambda: BrokenEncryption()
    )

    with pytest.raises(RuntimeError, match="encryption unavailable"):
        notifications.save_notifications(
            NotificationConfig(email={"smtp_password": "never-write-this"})
        )
    assert not notification_store.exists()


def test_corrupt_notification_store_fails_closed(notification_store):
    notification_store.write_text("not-json")
    with pytest.raises(RuntimeError, match="invalid"):
        notifications.load_notifications()


def test_corrupt_encrypted_secret_fails_even_for_redacted_views(notification_store):
    notification_store.write_text(
        json.dumps({"email": {"smtp_password_encrypted": "not-fernet"}})
    )

    with pytest.raises(ValueError, match="Failed to decrypt"):
        notifications.load_notifications()
