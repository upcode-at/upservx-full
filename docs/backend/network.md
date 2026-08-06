# Network Management

**File:** `upcode-harbor-service/network.py`
**API sub-module:** `upcode-harbor-service/api/network.py`

**Required permission:** Admin (`sudo`/`wheel`)

---

## Overview

The network module gives access to:

- **Network interfaces** (status, IP configuration, traffic)
- **Docker networks**
- **DNS configuration**

---

## Network Interfaces

### Information per Interface

```python
class NetworkInterface(BaseModel):
    name: str
    status: str         # "up", "down"
    mac: str
    ipv4: List[str]
    ipv6: List[str]
    type: str           # "ethernet", "wifi", "loopback", "docker", "bridge"
    rx_bytes: int
    tx_bytes: int
    rx_packets: int
    tx_packets: int
    duplex: str
    speed: int          # Mbit/s
```

Reads via `psutil.net_if_addrs()`, `psutil.net_if_stats()`, and `psutil.net_io_counters()`.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/network/interfaces` | All network interfaces |
| `GET` | `/network/interfaces/{name}` | Details of an interface |
| `POST` | `/network/interfaces/{name}/up` | Enable interface |
| `POST` | `/network/interfaces/{name}/down` | Disable interface |
| `POST` | `/network/interfaces/{name}/ip` | Assign IP address |
| `DELETE` | `/network/interfaces/{name}/ip` | Remove IP address |
| `GET` | `/network/docker` | All Docker networks |
| `POST` | `/network/docker` | Create Docker network |
| `DELETE` | `/network/docker/{name}` | Delete Docker network |
| `GET` | `/network/dns` | DNS configuration |
| `PUT` | `/network/dns` | Update DNS configuration |
| `GET` | `/network/stats` | Traffic statistics (all interfaces) |

---

## Interface Management

Commands are run via `subprocess`:

```python
# Enable interface
subprocess.run(["ip", "link", "set", name, "up"])

# Assign IP
subprocess.run(["ip", "addr", "add", ip_cidr, "dev", name])

# Remove IP
subprocess.run(["ip", "addr", "del", ip_cidr, "dev", name])
```

**Note:** These changes are not persistent without additional configuration (e.g. `/etc/network/interfaces` or `netplan`).

---

## Docker Networks

Docker networks are read via `docker network ls --format json`:

```python
class DockerNetwork(BaseModel):
    id: str
    name: str
    driver: str        # "bridge", "host", "overlay", etc.
    scope: str
    internal: bool
    ipam_config: List[dict]
```

---

## DNS Configuration

The DNS configuration is read from `/etc/resolv.conf`:

```python
class DNSConfig(BaseModel):
    nameservers: List[str]
    search: List[str]
    options: List[str]
```

Updates write the file back to `/etc/resolv.conf`.

**Security Note:** Writing to `/etc/resolv.conf` may be restricted in some environments (e.g. with systemd-resolved or NetworkManager).
