# Service Management

**File:** `upservx-service/services.py`
**API sub-module:** `upservx-service/api/services.py`

**Required permission:** Admin (`sudo`/`wheel`)

---

## Overview

The services module manages **systemd system services** on the host. It provides an interface to view, start, stop, restart, and enable/disable system services.

---

## Data Model: `SystemService`

```python
class SystemService(BaseModel):
    name: str
    description: str
    status: str           # "active", "inactive", "failed", "unknown"
    sub_status: str       # "running", "dead", "exited"
    enabled: bool         # Autostart on boot
    load_state: str       # "loaded", "not-found", "error"
    active_since: datetime
    pid: int
    memory_bytes: int
    cpu_percent: float
    unit_file: str        # Path to .service file
```

---

## Data Sources

Service information is read via `systemctl`:

```bash
systemctl list-units --type=service --all --output=json
systemctl show <service> --output=json
```

---

## Functions

| Function | Command |
|---|---|
| `get_services()` | `systemctl list-units --type=service --all` |
| `get_service_info(name)` | `systemctl show <name>` |
| `start_service(name)` | `systemctl start <name>` |
| `stop_service(name)` | `systemctl stop <name>` |
| `restart_service(name)` | `systemctl restart <name>` |
| `reload_service(name)` | `systemctl reload <name>` |
| `enable_service(name)` | `systemctl enable <name>` |
| `disable_service(name)` | `systemctl disable <name>` |
| `get_service_logs(name)` | `journalctl -u <name> -n 200` |
| `get_service_status(name)` | `systemctl is-active <name>` |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/services` | All system services |
| `GET` | `/services/{name}` | Service details |
| `POST` | `/services/{name}/start` | Start service |
| `POST` | `/services/{name}/stop` | Stop service |
| `POST` | `/services/{name}/restart` | Restart service |
| `POST` | `/services/{name}/reload` | Reload config |
| `POST` | `/services/{name}/enable` | Enable autostart |
| `POST` | `/services/{name}/disable` | Disable autostart |
| `GET` | `/services/{name}/logs` | Journald logs |

---

## Service Filtering

By default, all `.service` units are returned, including system services. The frontend provides filtering by:

- Status (active, inactive, failed)
- Search by name
- Hide system services (units from `/lib/systemd/system/`)

---

## Safety Notes

- Stopping critical services (e.g. `sshd`, `networking`, `systemd-*`) can lock you out of the system
- All service operations are logged in the activity log
- No confirmation dialog in the API itself – responsibility lies with the caller
