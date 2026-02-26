"""
Notification system for UpservX.

Handles email (SMTP) and webhook notifications.
Notification configuration is persisted to notifications.json.
"""

import os
import json
import smtplib
import ssl
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from models import NotificationConfig, NotificationEmailConfig, NotificationWebhookConfig, NotificationEvents

NOTIFICATIONS_FILE = os.path.join(os.path.dirname(__file__), "notifications.json")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def load_notifications() -> NotificationConfig:
    """Load notification configuration from file, returning defaults if missing."""
    if os.path.exists(NOTIFICATIONS_FILE):
        try:
            with open(NOTIFICATIONS_FILE) as f:
                data = json.load(f)
            return NotificationConfig(**data)
        except Exception:
            pass
    return NotificationConfig()


def save_notifications(config: NotificationConfig) -> None:
    """Persist notification configuration to file."""
    with open(NOTIFICATIONS_FILE, "w") as f:
        json.dump(config.dict(), f, indent=2)


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
        raise RuntimeError("SMTP authentication failed – check username and password")
    except smtplib.SMTPConnectError:
        raise RuntimeError(f"Could not connect to SMTP server {cfg.smtp_host}:{cfg.smtp_port}")
    except Exception as e:
        raise RuntimeError(f"Failed to send email: {e}")


def test_email(cfg: NotificationEmailConfig) -> dict:
    """Send a test email. Returns {'ok': True} or {'ok': False, 'error': str}."""
    try:
        send_email(cfg, "UpservX – Test Notification", "This is a test notification from UpservX.")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

def send_webhook(cfg: NotificationWebhookConfig, event: str, message: str) -> None:
    """POST a JSON payload to the configured webhook URL.

    Raises an exception with a human-readable message on failure.
    """
    if not cfg.url:
        raise ValueError("Webhook URL is not configured")

    payload = json.dumps({"event": event, "message": message, "source": "upservx"}).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "UpservX/1.0"}
    if cfg.secret:
        headers["X-UpservX-Secret"] = cfg.secret

    req = urllib.request.Request(cfg.url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in range(200, 300):
                raise RuntimeError(f"Webhook returned HTTP {resp.status}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Webhook request failed: {e.reason}")
    except Exception as e:
        raise RuntimeError(f"Webhook error: {e}")


def test_webhook(cfg: NotificationWebhookConfig) -> dict:
    """Send a test webhook payload. Returns {'ok': True} or {'ok': False, 'error': str}."""
    try:
        send_webhook(cfg, "test", "This is a test notification from UpservX.")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Dispatch helper (called from other modules)
# ---------------------------------------------------------------------------

def notify(event: str, message: str) -> None:
    """Send a notification for the given event if the event type is enabled.

    Silently ignores failures so callers are never interrupted.
    """
    try:
        config = load_notifications()

        # Check whether this event type is enabled
        events = config.events
        event_map = {
            "container_start":  events.container_start,
            "container_stop":   events.container_stop,
            "container_crash":  events.container_crash,
            "vm_start":         events.vm_start,
            "vm_stop":          events.vm_stop,
            "backup_success":   events.backup_success,
            "backup_failure":   events.backup_failure,
            "system_alert":     events.system_alert,
        }

        if not event_map.get(event, True):
            return

        subject = f"UpservX – {event.replace('_', ' ').title()}"

        if config.email.enabled:
            try:
                send_email(config.email, subject, message)
            except Exception:
                pass

        if config.webhook.enabled:
            try:
                send_webhook(config.webhook, event, message)
            except Exception:
                pass

    except Exception:
        pass
