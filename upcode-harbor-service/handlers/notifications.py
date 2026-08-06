"""
Notification system for Upcode Harbor.

Handles email (SMTP) and webhook notifications.
Notification configuration is persisted to notifications.json.
"""

import json
import socket
import smtplib
import ssl
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from lib.models import NotificationConfig, NotificationEmailConfig, NotificationWebhookConfig, NotificationEvents
from lib.logger import log_system
from lib.secure_store import SecureStoreError, secure_read_json, secure_write_json
from lib.encryption import get_encryption_manager

NOTIFICATIONS_FILE = "/etc/upcode-harbor/notifications.json"


def _get_node_name() -> str:
    """Return the node hostname from /etc/hostname, falling back to socket.gethostname()."""
    try:
        with open("/etc/hostname") as f:
            name = f.read().strip()
            if name:
                return name
    except Exception:
        pass
    return socket.gethostname() or "unknown"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _read_notification_data() -> dict:
    try:
        data = secure_read_json(NOTIFICATIONS_FILE, missing={})
    except SecureStoreError as error:
        raise RuntimeError("Notification configuration is invalid") from error
    if not isinstance(data, dict):
        raise RuntimeError("Notification configuration is invalid")
    return data


def load_notifications(*, include_secrets: bool = False) -> NotificationConfig:
    """Load notification settings without exposing stored secrets by default."""

    data = _read_notification_data()
    if not data:
        return NotificationConfig()
    encryption = get_encryption_manager()
    email = dict(data.get("email") or {})
    webhook = dict(data.get("webhook") or {})
    migrated = False

    legacy_password = email.pop("smtp_password", "")
    encrypted_password = email.get("smtp_password_encrypted", "")
    if legacy_password and not encrypted_password:
        encrypted_password = encryption.encrypt(legacy_password)
        email["smtp_password_encrypted"] = encrypted_password
        migrated = True
    decrypted_password = (
        encryption.decrypt(encrypted_password) if encrypted_password else ""
    )
    email["smtp_password"] = decrypted_password if include_secrets else ""

    legacy_secret = webhook.pop("secret", "")
    encrypted_secret = webhook.get("secret_encrypted", "")
    if legacy_secret and not encrypted_secret:
        encrypted_secret = encryption.encrypt(legacy_secret)
        webhook["secret_encrypted"] = encrypted_secret
        migrated = True
    decrypted_secret = encryption.decrypt(encrypted_secret) if encrypted_secret else ""
    webhook["secret"] = decrypted_secret if include_secrets else ""

    if migrated:
        stored = dict(data)
        stored["email"] = {key: value for key, value in email.items() if key != "smtp_password"}
        stored["webhook"] = {key: value for key, value in webhook.items() if key != "secret"}
        secure_write_json(NOTIFICATIONS_FILE, stored)

    return NotificationConfig(**{**data, "email": email, "webhook": webhook})


def save_notifications(config: NotificationConfig) -> None:
    """Persist notification configuration to file."""
    existing = _read_notification_data()
    existing_email = dict(existing.get("email") or {})
    existing_webhook = dict(existing.get("webhook") or {})
    data = config.model_dump()
    email = data["email"]
    webhook = data["webhook"]
    encryption = get_encryption_manager()

    password = email.pop("smtp_password", "")
    if password:
        email["smtp_password_encrypted"] = encryption.encrypt(password)
    elif existing_email.get("smtp_password_encrypted"):
        encryption.decrypt(existing_email["smtp_password_encrypted"])
        email["smtp_password_encrypted"] = existing_email["smtp_password_encrypted"]
    elif existing_email.get("smtp_password"):
        email["smtp_password_encrypted"] = encryption.encrypt(
            existing_email["smtp_password"]
        )

    secret = webhook.pop("secret", "")
    if secret:
        webhook["secret_encrypted"] = encryption.encrypt(secret)
    elif existing_webhook.get("secret_encrypted"):
        encryption.decrypt(existing_webhook["secret_encrypted"])
        webhook["secret_encrypted"] = existing_webhook["secret_encrypted"]
    elif existing_webhook.get("secret"):
        webhook["secret_encrypted"] = encryption.encrypt(existing_webhook["secret"])

    secure_write_json(NOTIFICATIONS_FILE, data)
    log_system("Notification configuration saved")


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def send_email(cfg: NotificationEmailConfig, subject: str, body: str) -> None:
    """Send an email using the supplied SMTP configuration.

    Raises an exception with a human-readable message on failure.
    """
    if not cfg.smtp_host:
        raise ValueError("SMTP host is not configured")
    if not cfg.to_addresses:
        raise ValueError("No recipient addresses configured")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.from_address or cfg.smtp_user
    msg["To"] = ", ".join(cfg.to_addresses)
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()

    try:
        if cfg.smtp_port == 465:
            # SSL from the start (SMTPS)
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=context) as server:
                if cfg.smtp_user and cfg.smtp_password:
                    server.login(cfg.smtp_user, cfg.smtp_password)
                server.sendmail(msg["From"], cfg.to_addresses, msg.as_string())
        else:
            # Plain → STARTTLS
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as server:
                if cfg.use_tls:
                    server.starttls(context=context)
                if cfg.smtp_user and cfg.smtp_password:
                    server.login(cfg.smtp_user, cfg.smtp_password)
                server.sendmail(msg["From"], cfg.to_addresses, msg.as_string())
    except smtplib.SMTPAuthenticationError:
        msg = "SMTP authentication failed – check username and password"
        log_system(f"Notification email error: {msg}", error=True)
        raise RuntimeError(msg)
    except smtplib.SMTPConnectError:
        msg = f"Could not connect to SMTP server {cfg.smtp_host}:{cfg.smtp_port}"
        log_system(f"Notification email error: {msg}", error=True)
        raise RuntimeError(msg)
    except Exception as e:
        log_system(f"Notification email error: {e}", error=True)
        raise RuntimeError(f"Failed to send email: {e}")
    log_system(f"Notification email sent to {', '.join(cfg.to_addresses)} – subject: {subject}")


def test_email(cfg: NotificationEmailConfig) -> dict:
    """Send a test email. Returns {'ok': True} or {'ok': False, 'error': str}."""
    try:
        send_email(cfg, "Upcode Harbor – Test Notification", "This is a test notification from Upcode Harbor.")
        log_system("Notification test email sent successfully")
        return {"ok": True}
    except Exception as e:
        log_system(f"Notification test email failed: {e}", error=True)
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

def _build_webhook_payload(url: str, event: str, message: str) -> bytes:
    """Build the correct JSON payload based on the webhook URL target."""
    url_lower = url.lower()

    if "discord.com/api/webhooks" in url_lower or "discordapp.com/api/webhooks" in url_lower:
        # Discord expects {"content": "..."} or embeds
        data = {
            "username": "Upcode Harbor",
            "embeds": [{
                "title": event.replace("_", " ").title(),
                "description": message,
                "color": 0xe74c3c if "fail" in event or "crash" in event or "delete" in event else 0x2ecc71,
            }]
        }
    elif "hooks.slack.com" in url_lower or "slack.com/services" in url_lower:
        # Slack incoming webhook
        data = {"text": f"*{event.replace('_', ' ').title()}*\n{message}"}
    else:
        # Generic / custom endpoint
        data = {"event": event, "message": message, "source": "upcode-harbor"}

    return json.dumps(data).encode()


def send_webhook(cfg: NotificationWebhookConfig, event: str, message: str) -> None:
    """POST a JSON payload to the configured webhook URL.

    Raises an exception with a human-readable message on failure.
    """
    if not cfg.url:
        raise ValueError("Webhook URL is not configured")

    payload = _build_webhook_payload(cfg.url, event, message)
    headers = {"Content-Type": "application/json", "User-Agent": "Upcode Harbor/1.0"}
    if cfg.secret:
        headers["X-Upcode-Harbor-Secret"] = cfg.secret

    req = urllib.request.Request(cfg.url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in range(200, 300):
                raise RuntimeError(f"Webhook returned HTTP {resp.status}")
    except urllib.error.URLError as e:
        log_system("Notification webhook connection failed", error=True)
        raise RuntimeError("Webhook request failed") from e
    except Exception as e:
        log_system("Notification webhook request failed", error=True)
        raise RuntimeError("Webhook request failed") from e
    log_system(f"Notification webhook sent – event: {event}")


def test_webhook(cfg: NotificationWebhookConfig) -> dict:
    """Send a test webhook payload. Returns {'ok': True} or {'ok': False, 'error': str}."""
    try:
        send_webhook(cfg, "test", "This is a test notification from Upcode Harbor.")
        log_system("Notification test webhook sent successfully")
        return {"ok": True}
    except Exception as e:
        log_system(f"Notification test webhook failed: {e}", error=True)
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Dispatch helper (called from other modules)
# ---------------------------------------------------------------------------

def notify(event: str, message: str) -> None:
    """Send a notification for the given event if the event type is enabled.

    Prepends the node hostname to every message.
    Silently ignores failures so callers are never interrupted.
    """
    try:
        node = _get_node_name()
        full_message = f"[Node: {node}] {message}"
        config = load_notifications(include_secrets=True)

        # Check whether this event type is enabled
        events = config.events
        event_map = {
            "container_create": events.container_create,
            "container_start":  events.container_start,
            "container_stop":   events.container_stop,
            "container_crash":  events.container_crash,
            "container_delete": events.container_delete,
            "vm_create":        events.vm_create,
            "vm_start":         events.vm_start,
            "vm_stop":          events.vm_stop,
            "vm_delete":        events.vm_delete,
            "backup_started":   events.backup_started,
            "backup_success":   events.backup_success,
            "backup_failure":   events.backup_failure,
            "replication_started": events.replication_started,
            "replication_success": events.replication_success,
            "replication_failure": events.replication_failure,
            "system_alert":     events.system_alert,
        }

        if not event_map.get(event, True):
            return

        log_system(f"Dispatching notification: event={event} – {full_message}")
        subject = f"[{node}] Upcode Harbor – {event.replace('_', ' ').title()}"

        if config.email.enabled:
            try:
                send_email(config.email, subject, full_message)
            except Exception as e:
                log_system(f"Notification email dispatch failed for event '{event}': {e}", error=True)

        if config.webhook.enabled:
            try:
                send_webhook(config.webhook, event, full_message)
            except Exception as e:
                log_system(f"Notification webhook dispatch failed for event '{event}': {e}", error=True)

    except Exception:
        pass
