# Notification System

**File:** `upservx-service/notifications.py`

**Required permission:** Admin (`sudo`/`wheel`)

---

## Overview

Upcode Harbor can send notifications to external services. Each notification has a **type** and a **payload**.

---

## Supported Notification Channels

| Channel | Description |
|---|---|
| **Webhook** | HTTP POST to a custom URL |
| **Email (SMTP)** | Via configured SMTP server |
| **Slack** | Via Slack Incoming Webhook |
| **Discord** | Via Discord Webhook |

---

## Data Model: `NotificationChannel`

```python
class NotificationChannel(BaseModel):
    id: str
    name: str
    type: str           # "webhook", "email", "slack", etc.
    enabled: bool
    config: Dict        # Channel-specific configuration
    events: List[str]   # Which events trigger this channel
```

---

## Event Types

| Event | Trigger |
|---|---|
| `container.start` | Container started |
| `container.stop` | Container stopped |
| `container.error` | Container exited with error |
| `vm.start` | VM started |
| `vm.stop` | VM stopped |
| `backup.success` | Backup completed successfully |
| `backup.error` | Backup failed |
| `system.high_cpu` | CPU usage > threshold |
| `system.high_memory` | Memory usage > threshold |
| `system.high_disk` | Disk usage > threshold |
| `user.login` | User login |
| `user.login_failed` | Failed login attempt |

---

## Channel Configuration Examples

### Webhook

Upcode Harbor sends `User-Agent: Upcode Harbor/1.0`. When a webhook secret is
configured, it is transmitted in the `X-Upcode-Harbor-Secret` header.

```json
{
  "url": "https://example.com/hook",
  "method": "POST",
  "headers": {"Authorization": "Bearer token"},
  "body_template": "{"event": "{event}", "message": "{message}"}"
}
```

### Email (SMTP)
```json
{
  "host": "smtp.example.com",
  "port": 587,
  "user": "alerts@example.com",
  "password": "secret",
  "from": "alerts@example.com",
  "to": ["admin@example.com"],
  "use_tls": true
}
```

### Telegram
```json
{
  "bot_token": "123456:ABC...",
  "chat_id": "-100123456789"
}
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/notifications/channels` | All notification channels |
| `POST` | `/notifications/channels` | Create channel |
| `PUT` | `/notifications/channels/{id}` | Edit channel |
| `DELETE` | `/notifications/channels/{id}` | Delete channel |
| `POST` | `/notifications/channels/{id}/test` | Send test notification |
| `GET` | `/notifications/history` | Notification history |
| `GET` | `/notifications/events` | Available event types |

---

## Internal Usage

Other modules trigger notifications via:

```python
from notifications import send_notification_event

await send_notification_event("container.stop", {
    "container": container_name,
    "exit_code": exit_code
})
```
