# Security Module

**File:** `upcode-harbor-service/handlers/security.py`  
**Router:** `upcode-harbor-service/api/security.py`  
**Prefix:** `/security`  
**Access:** Admin group (`sudo` / `wheel`) required for all endpoints

---

## Overview

The Security Module provides five separate subsystems under a single API prefix. All endpoints are admin-only; non-admin users do not see the Security entry in the sidebar.

The business logic lives in `handlers/security.py`; the FastAPI router in `api/security.py` is a thin mapping layer that calls those handler functions and wraps their output.

---

## 1. Fail2Ban Management

### Handler functions

| Function | Description |
|---|---|
| `get_all_fail2ban_jails()` | Calls `fail2ban-client status` to list all jail names, then calls `get_fail2ban_jail(name)` for each |
| `get_fail2ban_jail(name)` | Calls `fail2ban-client status <jail>` and parses banned IPs, total failed, active status |
| `unban_ip(jail, ip)` | Calls `fail2ban-client set <jail> unbanip <ip>` |

### Endpoints

#### `GET /security/fail2ban`
Returns a list of all configured Fail2Ban jails.

**Response (per jail):**
```json
{
  "name": "sshd",
  "active": true,
  "banned_count": 3,
  "total_failed": 142,
  "banned_ips": ["192.168.1.5", "10.0.0.7", "203.0.113.9"]
}
```

If Fail2Ban is not installed or `fail2ban-client` returns an error, the endpoint returns `{ "error": "<last line of stderr>" }` instead of crashing.

#### `POST /security/fail2ban/unban`
Unbans a single IP address from a jail.

**Request body:**
```json
{ "jail": "sshd", "ip": "192.168.1.5" }
```

**Response:**
```json
{ "success": true, "message": "Unbanned 192.168.1.5 from sshd" }
```

---

## 2. Package Upgrade Tracker

### Handler functions

| Function | Description |
|---|---|
| `get_upgradeable_packages()` | Runs `apt-get --simulate upgrade` and parses output |
| `upgrade_package(package_name=None)` | Runs `apt-get upgrade -y [<name>]`; name validated with regex |

**Note:** Both functions require `apt-get` and return `{ "not_available": true }` on non-Debian systems.

### Endpoints

#### `GET /security/packages`
Returns a list of all upgradeable packages.

**Response (per package):**
```json
{
  "name": "openssl",
  "current_version": "3.0.2-0ubuntu1.10",
  "new_version": "3.0.2-0ubuntu1.15",
  "is_security": true
}
```

#### `POST /security/packages/upgrade`
Upgrades all upgradeable packages. Runs with a 300-second timeout.

**Response:**
```json
{ "success": true, "upgraded": 12 }
```

#### `POST /security/packages/upgrade/{name}`
Upgrades a single package by name. The package name is validated against the regex `^[a-zA-Z0-9][a-zA-Z0-9.+\-]*$` before being passed to `apt-get` to prevent command injection.

**Response:**
```json
{ "success": true, "package": "openssl" }
```

---

## 3. SSL/TLS Certificate Inspector

### Handler function

| Function | Description |
|---|---|
| `get_certificates()` | Scans standard cert directories for `.crt` / `.pem` files and parses each with `openssl x509` |

**Scanned directories:**
- `/etc/ssl/certs/`
- `/etc/nginx/`
- `/etc/letsencrypt/live/`
- `/etc/apache2/`
- `/etc/haproxy/`

Files that are not valid X.509 certificates (e.g. CA bundles or private keys) are silently skipped.

### Endpoint

#### `GET /security/certificates`
Returns a list of discovered certificates.

**Response (per certificate):**
```json
{
  "path": "/etc/letsencrypt/live/example.com/cert.pem",
  "common_name": "example.com",
  "issuer": "Let's Encrypt",
  "expiry": "2026-07-15",
  "days_left": 73,
  "status": "valid"
}
```

**Status values:**
| Value | Condition |
|---|---|
| `valid` | `days_left` ≥ 30 |
| `expiring_soon` | 0 < `days_left` < 30 |
| `expired` | `days_left` ≤ 0 |

---

## 4. Open Port Scanner

### Handler function

| Function | Description |
|---|---|
| `get_open_ports()` | Runs `ss -tlnpu` and parses each LISTEN socket entry |

### Endpoint

#### `GET /security/ports`
Returns all currently listening sockets.

**Response (per port):**
```json
{
  "protocol": "tcp",
  "address": "0.0.0.0",
  "port": 22,
  "process": "sshd",
  "pid": 1234
}
```

**Frontend filters:**
- **Protocol:** All / TCP / UDP
- **Address:** All / Public (non-loopback) / Loopback (`127.x.x.x` or `::1`)

---

## 5. CVE Vulnerability Scanner

### Handler functions

| Function | Description |
|---|---|
| `scan_cves(limit=300)` | Enumerates installed packages via `dpkg-query`, batches OSV.dev queries in groups of 100 |
| `_get_dpkg_packages()` | Returns `[(name, version), ...]` from `dpkg-query -W -f` |
| `_get_ecosystem()` | Detects OS ecosystem (currently `Debian` or `PyPI` fallback) |

**External dependency:** `https://api.osv.dev/v1/querybatch` — no API key required, no data is transmitted that identifies the server beyond package names and versions.

### Endpoint

#### `GET /security/cve?limit=300`
Triggers a CVE scan and returns all findings sorted by severity.

**Query parameters:**
| Parameter | Default | Range | Description |
|---|---|---|---|
| `limit` | 300 | 50–1000 | Maximum number of packages to scan |

**Response (per finding):**
```json
{
  "id": "CVE-2024-12345",
  "package": "openssl",
  "version": "3.0.2-0ubuntu1.10",
  "cvss_score": 9.8,
  "severity": "critical",
  "summary": "Heap buffer overflow in OpenSSL X.509 name parsing"
}
```

**Severity mapping:**
| Severity | CVSS Score Range |
|---|---|
| `critical` | ≥ 9.0 |
| `high` | 7.0 – 8.9 |
| `medium` | 4.0 – 6.9 |
| `low` | 0.1 – 3.9 |
| `unknown` | No CVSS score available |

Results are sorted: Critical → High → Medium → Low → Unknown, then by CVSS score descending within each group.

---

## Access Control

All `/security/*` endpoints are protected by the standard admin permission check (`sudo` / `wheel` group). The Security tab in the frontend sidebar is hidden from non-admin users via the `requires: "admin"` attribute on the sidebar entry.

API tokens require an appropriate role and matching `admin:read` or
`admin:write` scope. Cluster principals cannot access these routes.
