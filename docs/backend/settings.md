# Settings

**File:** `upservx-service/handlers/settings.py`
**API sub-module:** `upservx-service/api/settings.py`

**Required permission:** Admin for write; read access for `/settings/customization`

---

## Overview

The settings module manages the globally configurable options of Upcode Harbor. Settings are stored in a JSON file at `/etc/upservx/settings.json`.

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
  "instance_name": "Upcode Harbor",
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

## API token management

API tokens are not part of `settings.json`. They are held in the owner-only
`/etc/upservx/api_tokens.json` token store as hashes with role, scopes, expiry,
and revocation metadata. The raw token is shown exactly once at creation. See
[Authentication and sessions](./authentication.md#api-tokens).

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/settings` | All settings (admin only) |
| `POST` | `/settings` | Update settings |
| `GET` | `/settings/customization` | Public branding info |
| `GET` | `/settings/api-tokens` | List token metadata |
| `POST` | `/settings/api-tokens` | Create a scoped API token |
| `DELETE` | `/settings/api-tokens/{token_id}` | Revoke an API token |
| `POST` | `/settings/test-notification` | Send test notification |
| `GET` | `/settings/version` | Upcode Harbor version info |
