# Installation & Deployment

## System Requirements

| Requirement | Minimum |
|---|---|
| Operating System | Linux Debian |
| Python | 3.11 or higher |
| Node.js | 20 or higher |
| Docker, LXD, libvirt/KVM, K3s | Optional profiles |
| Root Access | Required to run the installer and signed updater |

---

## Quick Installation

```bash
git clone --recurse-submodules https://github.com/upcode-at/upservx.git
cd upservx
sudo ./install.sh
```

The `install.sh` script handles:

- Installing a minimal core package set and only explicitly selected profiles
- Creating dedicated `upservx` backend/worker and `upservx-web` accounts
- Installing an immutable root-owned release below `/opt/upservx/releases`
- Installing locked dependencies with `npm ci` and `requirements.lock`
- Creating separate API, frontend, worker, health, and update systemd units
- Installing a backend-only, allowlisted root helper and sudoers rule
- Exposing loopback-only application ports through an HTTPS nginx proxy
- Running the post-install privilege and health smoke test

If a run was interrupted after the immutable release was created, rebuild its
configuration and finish the remaining initialization without reinstalling
packages or overwriting the release:

```bash
sudo ./install.sh --resume
```

The installer generates all node-local key material automatically: the nginx
TLS certificate and private key, the application encryption key, the session
signing secret, and the cluster CA/certificate/private key. A release public key
cannot be generated locally because it must match the external update signer;
signed updates therefore remain disabled unless `--update-public-key` is used.

For a clean restart after a broken installation, use `--reinstall`. The
installer stops UpservX, moves the existing release, secrets, state, web state,
logs, update trust, and managed system integration files into a mode-`0700`
recovery directory below
`/var/backups/upservx/`, and then performs a fresh installation with newly
generated local keys:

```bash
sudo ./install.sh --reinstall
```

Run this command from a separate source checkout. It is intentionally rejected
when `install.sh` itself is located below `/opt/upservx`.

To enable signed updates, supply the release public key:

```bash
sudo ./install.sh --profile containers \
  --update-public-key /secure/release-public.pem
```

Available profiles are `core` (the default), `containers`, `virtualization`,
`cluster`, and `full`. Individual `--with-*` flags are listed by
`./install.sh --help`. No keys or checksum environment variables are required.
Without `--update-public-key`, the update facility stays disabled. NodeSource,
Docker, and K3s use their official HTTPS sources by default; optional SHA-256
environment variables add explicit pinning. K3s installs its compatible
`kubectl` by default. If `KUBECTL_VERSION` selects a separate version, the
installer fetches and validates its official checksum when `KUBECTL_SHA256` is
not supplied.

---

## Manual Installation

### Backend (`upservx-service`)

```bash
cd upservx-service
pip install --no-deps -r requirements.lock

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
npm ci
npm run build
npm start      # Production mode on port 9200
# or
npm run dev    # Development mode with Turbopack
```

---

## Service Architecture (systemd)

The installer configures these systemd units:

| Service | Description |
|---|---|
| `upservx-api.service` | Loopback FastAPI API on port 9500 and cluster TLS transport on port 9501 |
| `upservx-web.service` | Loopback Next.js frontend on port 9200 |
| `upservx-worker.service` | Persistent transactional job worker |
| `upservx-health.timer` | Recurring liveness probe and recovery trigger |
| `upservx-update@.service` | Independent root unit for one signed release |

The browser-facing frontend and `/api` proxy must be served over HTTPS. Port
9200 and the backend's port 9500 are upstream listeners, not production browser
entry points. The default secure session cookie is intentionally not sent over
plain HTTP. Terminate TLS at Nginx or another trusted reverse proxy and forward
`/` to port 9200, `/api/` to port 9500, and WebSocket upgrades under `/ws/`.
Do not disable `UPSERVX_COOKIE_SECURE` in production.

---

## Configuration Files

| File / Path | Content |
|---|---|
| `/etc/upservx/encryption.key` | Fernet encryption key (chmod 600) |
| `/etc/upservx/.session_secret` | Session-signing secret (chmod 600) |
| `/etc/upservx/sessions.json` | Hashed, revocable session records (chmod 600) |
| `/etc/upservx/api_tokens.json` | Hashed API-token records (chmod 600) |
| `/etc/upservx/notifications.json` | Email & webhook configuration |
| `/etc/upservx/alerts.json` | Alert thresholds |
| `/etc/upservx/metrics/` | Historical metrics (JSON) |
| `/etc/upservx/nodes/` | Cluster node configurations |
| `/etc/upservx/master` | Cluster master configuration |
| `/etc/upservx/child` | Cluster child configuration |
| `/etc/upservx/cluster-security/` | Node-local CA, certificate, and private keys (private files chmod 600) |
| `/var/log/upservx/api.log` | API log |
| `/var/log/upservx/worker.log` | Worker log |
| `/var/log/upservx/activity.log` | Structured activity log |
| `/var/lib/upservx/app-store/` | Mutable app store templates (`/opt/upservx/app-store` is a compatibility link) |
| `/var/lib/upservx/compose/` | Installed Docker Compose projects (`/opt/upservx/compose` is a compatibility link) |
| `/var/lib/upservx/app-data/` | Per-project managed App Store bind data |
| `/etc/upservx/settings.json` | Application settings (hostname, timezone, SSH and monitoring options) |
| `/etc/upservx/proxy_config.json` | Nginx proxy metadata |
| `upservx-service/network_settings.json` | Network settings |

---

## Update

Updates never use Git inside `/opt/upservx`. Build a versioned artifact on the
release system and sign it with the offline/private release key:

```bash
deploy/build-release-artifact 1.2.3 /secure/release-private.pem /tmp/upservx-1.2.3
```

Copy the three output files into
`/var/lib/upservx/updates/1.2.3/` as root, make them root-owned and not writable
by group/other, and write `1.2.3` to the root-owned mode-`0640`
`/var/lib/upservx/updates/latest` marker. The Settings update action then queues
the external `upservx-update@1.2.3.service` unit.

The updater verifies the SHA-256 and detached signature, backs up
`/etc/upservx`, builds the new immutable release, switches
`/opt/upservx/current` atomically, performs readiness checks, and rolls back on
failure. Its non-zero exit code and error are preserved in the persistent job.
See [`../deploy/README.md`](../deploy/README.md) for the exact artifact names.

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `FRONTEND_ORIGINS` | Comma-separated list of allowed CORS origins | All server IPs auto-detected |
| `UPSERVX_SESSION_TTL_SECONDS` | User-session lifetime in seconds | `3600` |
| `UPSERVX_COOKIE_SECURE` | Require HTTPS for the session cookie | `true` |
| `UPSERVX_COOKIE_SAMESITE` | Session-cookie SameSite policy | `strict` |
| `UPSERVX_COOKIE_DOMAIN` | Optional explicit session-cookie domain | unset |

All directories under `/etc/upservx` are enforced as `0700` and all regular
files as `0600` at startup. Symlinks in the configuration tree fail the
security initialization rather than being followed.

---

## Paths Requiring Root Privileges

- `/etc/upservx/` – Owner-only configuration (`upservx`)
- `/var/log/upservx/` – Backend logs (`upservx`)
- `/etc/nginx/` – Nginx configuration
- `/etc/letsencrypt/` – SSL certificates
- `/etc/ssh/sshd_config` – Read SSH configuration
- `/etc/hosts` – Set hostname
- Read systemd journal (`journalctl`)
- `nft` – Firewall rules
- `docker` – Container management
- `virsh` / `qemu-img` – VM management

The web process has no privileged access. Docker, LXD, and libvirt/KVM groups
are added to the backend account only for selected profiles. All other host
mutations go through `/usr/local/libexec/upservx-privileged`; the sudoers policy
permits that helper and no other root command. Run the installed audit with:

```bash
sudo /usr/local/libexec/upservx-post-install-smoke
```
