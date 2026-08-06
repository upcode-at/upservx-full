# Firewall Management

**File:** `upservx-service/firewall.py`
**API sub-module:** `upservx-service/api/firewall.py`

**Required permission:** Admin (`sudo`/`wheel`)

---

## Overview

Upcode Harbor manages firewall rules via **nftables** and/or **iptables**, depending on which tool is active on the system.

---

## Backend Detection

```python
if shutil.which("nft"):
    BACKEND = "nftables"
elif shutil.which("iptables"):
    BACKEND = "iptables"
else:
    BACKEND = None
```

All operations use the detected backend. If neither is available, firewall endpoints return an appropriate error.

---

## Data Model: `FirewallRule`

```python
class FirewallRule(BaseModel):
    id: str
    chain: str          # "INPUT", "OUTPUT", "FORWARD"
    protocol: str       # "tcp", "udp", "icmp", "all"
    source: str         # IP or CIDR, "" = any
    destination: str    # IP or CIDR, "" = any
    port: str           # Port or range, "" = any
    action: str         # "ACCEPT", "DROP", "REJECT"
    comment: str
    enabled: bool
```

---

## nftables

Rules are stored in `/etc/nftables.conf` or managed via the `nft` CLI.

Key commands:
```bash
nft list ruleset
nft add rule inet filter input ...
nft delete rule inet filter input handle <id>
nft flush chain inet filter input
```

---

## iptables

Fallback when nftables is unavailable.

Key commands:
```bash
iptables -L -n --line-numbers
iptables -A INPUT -p tcp --dport <port> -j ACCEPT
iptables -D INPUT <line_number>
iptables-save > /etc/iptables/rules.v4
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/firewall/rules` | All firewall rules |
| `POST` | `/firewall/rules` | Add new rule |
| `PUT` | `/firewall/rules/{id}` | Update rule |
| `DELETE` | `/firewall/rules/{id}` | Delete rule |
| `POST` | `/firewall/rules/{id}/enable` | Enable rule |
| `POST` | `/firewall/rules/{id}/disable` | Disable rule |
| `GET` | `/firewall/status` | Active backend and default policies |
| `POST` | `/firewall/flush` | Clear all rules |
| `GET` | `/firewall/export` | Export as nftables/iptables script |
| `POST` | `/firewall/import` | Import from script |

---

## Default Policies

The system default can be set per chain:

| Chain | Default Options |
|---|---|
| `INPUT` | `ACCEPT` or `DROP` |
| `OUTPUT` | `ACCEPT` or `DROP` |
| `FORWARD` | `ACCEPT` or `DROP` |

**Warning:** Setting INPUT to DROP without an SSH ACCEPT rule will lock out SSH access.
