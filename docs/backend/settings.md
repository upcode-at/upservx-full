# Settings

**File:** `upservx-service/handlers/settings.py`
**API sub-module:** `upservx-service/api/settings.py`

**Required permission:** Admin for write; read access for `/settings/customization`

---

## Overview

The settings module manages the globally configurable options of UpservX. Settings are stored in a JSON file at `/etc/upservx/settings.json`.

VPN/OpenVPN profiles uploaded via the Settings API are stored in `/etc/upservx/vpn` (for example `/etc/upservx/vpn/client.ovpn`).

---

## Settings Structure

```python
class Settings(BaseModel):
    # Appearance
    instance_name: str          # e.g. "My Server"
    theme: str                  # "dark", "light", "system"
    logo_url: str               # Custom logo URL
    favicon_url: str            # Custom favicon
    accent_color: str           # Hex color code

    # Authentication
    api_key: str                # Bearer API key (hashed)
    session_timeout_minutes: int  # Default: 60

    # Notifications
    notification_channels: List[dict]  # Embedded channel configs

    # Monitoring
    metrics_interval_seconds: int   # Default: 60
    alert_cpu_percent: int          # Default: 90
    alert_memory_percent: int       # Default: 85
    alert_disk_percent: int         # Default: 90

    # Updates
    auto_update_check: bool         # Default: true
    update_channel: str             # "stable", "beta"

    # Backup
    backup_dir: str                 # Default: /var/backups/upservx

    # Security
    allowed_origins: List[str]      # CORS whitelist
    rate_limit_enabled: bool
```

---

## Configuration File

```json
// /etc/upservx/settings.json
{
  "instance_name": "UpservX",
  "theme": "dark",
  "metrics_interval_seconds": 60,
  "alert_cpu_percent": 90,
  "alert_memory_percent": 85,
  "alert_disk_percent": 90,
  "auto_update_check": true,
  "update_channel": "stable",
  "backup_dir": "/var/backups/upservx",
  "rate_limit_enabled": true
}
```

---

## Customization

The `/settings/customization` endpoint is **public** (no authentication required) and is loaded on the login page:

```json
{
  "instance_name": "My Server",
  "logo_url": "/custom/logo.png",
  "favicon_url": "/custom/favicon.ico",
  "accent_color": "#6366f1",
  "theme": "dark"
}
```

This allows the login screen to display branding without requiring login first.

---

## API Key Management

```python
# Generate API key
import secrets
api_key = secrets.token_urlsafe(32)

# Store hashed
import hashlib
settings.api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
```

The raw key is only shown once when generated and is not stored in plaintext.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/settings` | All settings (admin only) |
| `PUT` | `/settings` | Update settings |
| `GET` | `/settings/customization` | Public branding info |
| `POST` | `/settings/api-key/generate` | Generate new API key |
| `DELETE` | `/settings/api-key` | Revoke API key |
| `POST` | `/settings/test-notification` | Send test notification |
| `GET` | `/settings/version` | UpservX version info |
