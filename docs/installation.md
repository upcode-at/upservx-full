# Installation & Deployment

## System Requirements

| Requirement | Minimum |
|---|---|
| Operating System | Linux Debian |
| Python | 3.8 or higher |
| Node.js | 18.0 or higher |
| Docker | Latest version |
| Root Access | Required for system management features |

---

## Quick Installation

```bash
git clone https://github.com/upcode-at/upservx.git
cd upservx
chmod +x install.sh
./install.sh
```

The `install.sh` script handles:
- Installing dependencies (Python packages, Node packages)
- Creating directories (`/etc/upservx`, `/var/log/upservx`, `/opt/upservx`)
- Setting up system services (systemd units)
- Generating the encryption key (`/etc/upservx/encryption.key`)
- Running database migrations (Alembic)

---

## Manual Installation

### Backend (`upservx-service`)

```bash
cd upservx-service
pip install -r requirements.txt

# Initialize database
alembic upgrade head

# Generate encryption key
python generate_encryption_key.py

# Start the public API and mandatory cluster HTTPS listener
python main.py
```

### Frontend (`upservx`)

```bash
cd upservx
npm install
npm run build
npm start      # Production mode on port 9200
# or
npm run dev    # Development mode with Turbopack
```

---

## Service Architecture (systemd)

Two systemd services are typically configured:

| Service | Description |
|---|---|
| `upservx-backend.service` | FastAPI API on port 9500 and cluster HTTPS transport on port 9501 |
| `upservx-frontend.service` | Next.js frontend on port 9200 |

---

## Configuration Files

| File / Path | Content |
|---|---|
| `/etc/upservx/encryption.key` | Fernet encryption key (chmod 600) |
| `/etc/upservx/notifications.json` | Email & webhook configuration |
| `/etc/upservx/alerts.json` | Alert thresholds |
| `/etc/upservx/metrics/` | Historical metrics (JSON) |
| `/etc/upservx/nodes/` | Cluster node configurations |
| `/etc/upservx/master` | Cluster master configuration |
| `/etc/upservx/child` | Cluster child configuration |
| `/etc/upservx/cluster-security/` | Node-local CA, certificate, and private keys (private files chmod 600) |
| `/etc/upservx.log` | Main log file (stdout/stderr) |
| `/var/log/upservx/activity.log` | Structured activity log |
| `/opt/upservx/app-store/` | App store templates |
| `/opt/upservx/compose/` | Installed Docker Compose projects |
| `upservx-service/settings.json` | Application settings (hostname, timezone, API key) |
| `upservx-service/proxy_config.json` | Nginx proxy configurations |
| `upservx-service/network_settings.json` | Network settings |

---

## Update

```bash
chmod +x update.sh
./update.sh
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `FRONTEND_ORIGINS` | Comma-separated list of allowed CORS origins | All server IPs auto-detected |

---

## Paths Requiring Root Privileges

- `/etc/upservx/` – Configuration (root)
- `/var/log/upservx/` – Logs (root)
- `/etc/nginx/` – Nginx configuration
- `/etc/letsencrypt/` – SSL certificates
- `/etc/ssh/sshd_config` – Read SSH configuration
- `/etc/hosts` – Set hostname
- Read systemd journal (`journalctl`)
- `nft` – Firewall rules
- `docker` – Container management
- `virsh` / `qemu-img` – VM management
