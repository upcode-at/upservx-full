# Logging

**File:** `upservx-service/upservx_logger.py`

**Required permission:** `adm` or `log` group (or admin) for log access

---

## Overview

Upcode Harbor uses two parallel logging systems:

1. **Activity Log** — Structured JSON log of user actions
2. **System Log** — stdout/stderr of the backend process

---

## Activity Log

**File:** `/var/log/upservx/activity.log`

All user actions are logged as structured JSON entries:

```json
{
  "timestamp": "2024-01-15T14:30:00Z",
  "user": "admin",
  "ip": "192.168.1.10",
  "method": "POST",
  "path": "/containers/nginx/stop",
  "status_code": 200,
  "duration_ms": 145,
  "body": {"reason": "maintenance"},
  "user_agent": "Mozilla/5.0 ..."
}
```

---

## Logger Implementation

```python
class UpcodeHarborLogger:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self._lock = asyncio.Lock()

    async def log(self, entry: dict):
        async with self._lock:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
```

The logger is async-safe and uses file locking to prevent concurrent write conflicts.

---

## System Log (TeeWriter)

The `main.py` installs a `_TeeWriter` that duplicates stdout/stderr to a log file:

```python
class _TeeWriter:
    def __init__(self, original, filepath):
        self.original = original
        self.file = open(filepath, 'a')

    def write(self, data):
        self.original.write(data)
        self.file.write(data)

sys.stdout = _TeeWriter(sys.stdout, "/etc/upservx.log")
sys.stderr = _TeeWriter(sys.stderr, "/etc/upservx.log")
```

**File:** `/etc/upservx.log`

This log captures all startup messages, Python exceptions, and `print()` output.

---

## Log Levels

| Level | Usage |
|---|---|
| `DEBUG` | Detailed debug information (disabled in production) |
| `INFO` | Normal operational messages |
| `WARNING` | Non-critical issues |
| `ERROR` | Errors – operation failed but service still running |
| `CRITICAL` | Critical errors – service may be compromised |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/logs/activity` | Activity log (paginated) |
| `GET` | `/logs/activity?user=admin` | Filter by user |
| `GET` | `/logs/activity?from=2024-01-01&to=2024-01-31` | Filter by date |
| `GET` | `/logs/system` | System log (last N lines) |
| `DELETE` | `/logs/activity` | Clear activity log (admin) |
| `GET` | `/logs/download` | Download log as file |

---

## Log Rotation

The activity log should be rotated externally via `logrotate`:

```
# /etc/logrotate.d/upservx
/var/log/upservx/activity.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    postrotate
        pkill -HUP -f "upservx-service"
    endscript
}
```
