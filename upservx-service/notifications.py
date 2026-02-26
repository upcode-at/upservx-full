"""
Notification system for UpservX.

Handles email (SMTP) and webhook notifications.
Notification configuration is persisted to notifications.json.
"""

import os
import json
import socket
import smtplib
import ssl
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from models import NotificationConfig, NotificationEmailConfig, NotificationWebhookConfig, NotificationEvents
from upservx_logger import log_system

NOTIFICATIONS_FILE = "/etc/upservx/notifications.json"


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
    os.makedirs(os.path.dirname(NOTIFICATIONS_FILE), exist_ok=True)
    with open(NOTIFICATIONS_FILE, "w") as f:
        json.dump(config.dict(), f, indent=2)
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
        send_email(cfg, "UpservX – Test Notification", "This is a test notification from UpservX.")
        log_system("Notification test email sent successfully")
        return {"ok": True}
    except Exception as e:
        log_system(f"Notification test email failed: {e}", error=True)
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
        log_system(f"Notification webhook error: {e.reason}", error=True)
        raise RuntimeError(f"Webhook request failed: {e.reason}")
    except Exception as e:
        log_system(f"Notification webhook error: {e}", error=True)
        raise RuntimeError(f"Webhook error: {e}")
    log_system(f"Notification webhook sent to {cfg.url} – event: {event}")


def test_webhook(cfg: NotificationWebhookConfig) -> dict:
    """Send a test webhook payload. Returns {'ok': True} or {'ok': False, 'error': str}."""
    try:
        send_webhook(cfg, "test", "This is a test notification from UpservX.")
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
        config = load_notifications()

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
            "backup_success":   events.backup_success,
            "backup_failure":   events.backup_failure,
            "system_alert":     events.system_alert,
        }

        if not event_map.get(event, True):
            return

        log_system(f"Dispatching notification: event={event} – {full_message}")
        subject = f"[{node}] UpservX – {event.replace('_', ' ').title()}"

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
