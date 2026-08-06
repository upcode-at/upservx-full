WireGuard is a fast, modern, and secure VPN protocol built directly into the Linux kernel. This template uses **wg-easy**, which adds a clean web UI on top of WireGuard for managing clients, generating QR codes, and monitoring connections.

## Features

- 🛡️ State-of-the-art cryptography (ChaCha20, Poly1305, Curve25519)
- ⚡ Extremely fast and lightweight compared to OpenVPN/IPSec
- 🌐 Web UI for client management (wg-easy)
- 📱 QR code generation for mobile clients (iOS/Android)
- 📊 Connection status and traffic monitoring
- 🔑 Simple key management
- 🔄 Automatic reconnection and persistent keepalive

## Prerequisites

The `wireguard` kernel module must be available on the host:

```bash
# Check if WireGuard is available
modprobe wireguard && echo "WireGuard OK"

# On Debian/Ubuntu (if needed):
apt install wireguard-tools
```

## Configuration

Before starting, set the required environment variables in `docker-compose.yml`:

**1. Set your server's public IP or domain:**
```yaml
- WG_HOST=your-server-ip-or-domain
```

**2. Generate a secure password hash:**
```bash
docker run --rm ghcr.io/wg-easy/wg-easy wgpw YOUR_PASSWORD
```
Copy the output and set it as `PASSWORD_HASH`.

**3. Start the container:**
```bash
docker compose up -d
```

## Default Access

| Service | URL |
|---|---|
| Web UI | `http://<your-server>:51821` |
| VPN Port | `51820/UDP` |

## Adding Clients

1. Open the Web UI at `http://<your-server>:51821`
2. Log in with your password
3. Click **+ New Client** and give it a name
4. Download the `.conf` file or scan the QR code with the WireGuard mobile app

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upcode-harbor/data/wireguard` | WireGuard config, keys, and client configs |

## Split Tunnel vs Full Tunnel

- **Full tunnel** (default): `WG_ALLOWED_IPS=0.0.0.0/0` – all traffic through VPN
- **Split tunnel**: `WG_ALLOWED_IPS=10.8.0.0/24` – only VPN subnet traffic

## Official Documentation

https://github.com/wg-easy/wg-easy
