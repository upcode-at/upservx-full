# Changelog

All notable changes to UpservX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [0.2.0] - 2026-02-26

> Full release notes: [releases/0.2.0.md](releases/0.2.0.md)

### Added
- **Notification System**: New push notification system that alerts on container, VM and backup events via Email (SMTP) and Webhook
  - Configuration persisted to `/etc/upservx/notifications.json`
  - **Email**: SMTP with STARTTLS (port 587) or SSL (port 465), multiple recipients, configurable From address, test button
  - **Webhook**: HTTP POST to any URL with optional `X-UpservX-Secret` header; auto-detects endpoint type:
    - Discord → rich Embed with title, description and colour coding (green = success, red = failure/delete)
    - Slack → Incoming Webhook `{"text": "..."}` format
    - Custom / generic → `{"event": ..., "message": ..., "source": "upservx"}`
  - **Node prefix**: every notification includes the originating node hostname (`[Node: hostname]`) in both subject and body
  - **Email subject** format: `[hostname] UpservX – Event Name`
  - **12 per-event toggles** (all enabled by default): Container create/start/stop/crash/delete, VM create/start/stop/delete, Backup success/failure, System alert
  - **Event integration**: `notify()` fires after the action is committed in all relevant modules — `api/containers.py` (Docker/LXC), `vms.py`, `execute_backup.py` (cron), `main.py` (manual trigger)
  - **Rich context per event**:
    - Container create — image, port mappings, volume mounts
    - Container start/stop/delete — container type (DOCKER / LXC / K8S)
    - VM create — CPU cores, memory MB, network bridge, disk count
    - VM stop — "has been shut down"; VM delete — "has been permanently deleted"
    - Backup success — size in MB, backup path
    - Backup failure — full error message
  - All notification operations (config save, email send, webhook post, dispatch) are written to the activity log
  - **Settings UI**: new fourth tab "Notifications" in Settings with Email card, Webhook card and Events card
  - API routes: `GET /settings/notifications`, `POST /settings/notifications`, `POST /settings/notifications/test/email`, `POST /settings/notifications/test/webhook`
- **Structured Activity Logging**: All service modules now write human-readable activity entries to `/var/log/upservx/activity.log` via the `upservx_logger` module
  - `log_container` — container lifecycle events, Docker/LXC volume & storage pool create/delete, image pull & delete (`containers.py`, `api/images.py`)
  - `log_vm` — VM create, start, stop, delete, clone, update, snapshot create/delete/restore (`vms.py`)
  - `log_storage` — drive mount/unmount/format, ZFS pool creation (`storage.py`)
  - `log_network` — network interface configuration, DNS settings save (`network.py`)
  - `log_user` — system user and group create/update/delete (`users.py`)
  - `log_service` — systemd service start/stop/enable/disable (`services.py`)
  - `log_firewall` — firewall rule add/delete, chain flush, chain policy, port forwarding, masquerade, ruleset save/load (`firewall.py`)
  - `log_proxy` — reverse proxy config create/delete, SSL certificate obtain/renew/revoke (`reverse_proxy.py`)
  - `log_appstore` — app install/uninstall (`app_store.py`)
  - `log_iso` — ISO download, upload, delete (`isos.py`)
  - `log_ssh` — SSH key pair generate/store/delete, authorized_keys setup (`ssh_keys.py`)
- **Cluster activity logging**: All 174 `print()` debug statements in `api/cluster.py` (`[CLUSTER]`, `[REPLICATION]`, `[IMPORT]`, `[EXPORT]`, `[RESOURCES]`, `[METRICS]`, `[UPLOAD]`, `[DOWNLOAD]` tags) are now routed through a `_clog()` helper that writes simultaneously to stdout and the activity log — 39 error/failure lines are logged at ERROR level
- Automatic `/etc/fstab` management when mounting drives via Storage Management UI
- Unmount functionality with automatic fstab cleanup
- UUID-based device identification for stable mounting
- Intelligent mount options based on filesystem type (ext4, ntfs, vfat, exfat, xfs)
- Automatic fstab backup before modifications
- **Cluster Replication System**: New Replication table in Cluster Management UI with columns for Origin Node, Destination Node, Name, Type and Sync Schedule
- Replication form with dynamic resource loading from selected origin node (containers and VMs)
- Replication configuration persisted to `/etc/upservx/replications.json`
- Manual replication trigger via green Play button per replication entry
- Container export with full Docker image (`docker save`), volumes, port mappings, environment variables, restart policy and command
- Container import with `docker load`, volume restoration and port mapping recreation
- VM export via `virsh dumpxml` including all disk images (`.qcow2`) as tar.gz archive
- VM import via `virsh define` with automatic disk path patching and UUID regeneration so libvirt generates a new one on the destination node
- Replication API endpoints: `POST /cluster/replications`, `GET /cluster/replications`, `DELETE /cluster/replications/{id}`, `POST /cluster/replications/{id}/trigger`
- Replication execution endpoints: `POST /cluster/export/{type}/{name}`, `GET /cluster/download/{filename}`, `POST /cluster/upload`, `POST /cluster/import/{type}`
- Cluster master key accepted as Bearer token in auth middleware for internal node-to-node requests
- Child node config now stores `cluster_key` field in addition to `key` for forward compatibility

### Changed
- All `print()` warning statements in `vms.py` replaced with `log_vm(..., error=True)` — warnings now appear in the activity log instead of being silently swallowed in production
- `app_store.py` and `storage.py` error prints replaced with structured log calls
- Improved fstab formatting with properly aligned columns
- Mount operations now create persistent entries automatically
- Cluster metrics endpoint moved from `/metrics` to `/cluster/node/metrics` to avoid conflicts with system metrics
- Auth middleware now also accepts master cluster key as Bearer token (in addition to API key and child cluster key)
- All replication endpoints handle both `cluster_key` and `key` fields in child config for backwards compatibility
- Replication endpoints (`/cluster/export`, `/cluster/download`, `/cluster/upload`, `/cluster/import`) bypass global PAM middleware and handle auth internally

### Fixed
- Storage mount operations now survive system reboots
- Container double-counting in cluster overview: Docker Compose containers were previously counted twice (once as Docker and once as Compose type)
- 401 Unauthorized errors on child nodes when master initiates replication upload
- `bytes` object has no attribute `encode` error during VM/container import (`text=True` removed from `subprocess.run` when binary input is used)

### Security
- **WebSocket shell auth**: `/system/shell` WebSocket endpoint now authenticates via PAM before accepting the connection — previously any unauthenticated client could open an interactive root shell
- **Debug endpoint removed**: `/debug/echo` endpoint replaced with a 404 — previously exposed arbitrary request reflection  
- **Path traversal (ISO)**: `isos.py` — `_safe_iso_path()` helper added; all ISO path operations now use `os.path.realpath()` to prevent `../../etc/passwd`-style traversal
- **SSRF (ISO download)**: `download_iso()` now rejects non-http/https schemes and blocks private/loopback/RFC-1918 address ranges
- **Path traversal (tarfile)**: `cluster.py` — `_safe_tar_extractall()` strips path components and rejects entries that would escape the extract directory (CVE-2007-4559 class)
- **Exception detail leak**: `/auth/login` no longer forwards exception messages to the client; internal errors return a generic "invalid credentials" message
- **Rate limiting**: `/auth/login` is now rate-limited to 10 attempts per IP per 60 seconds to slow brute-force attacks
- **Stale middleware bypass removed**: `/metrics` was incorrectly excluded from PAM auth (the actual cluster metrics route is `/cluster/node/metrics` and is authenticated)
- **Input validation (users)**: `users.py` — `_validate_name()` regex guard added and called in every user/group management function (`create_user`, `update_user`, `delete_user`, `create_group`, `update_group`, `delete_group`); rejected names containing shell metacharacters prevent command injection through subprocess calls
- **Path traversal (SSH keys)**: `ssh_keys.py` — `_safe_key_path()` helper added; `key_name` is validated against `^[a-zA-Z0-9_\-\.]{1,64}$` and path is verified to stay within `./ssh_keys/` in `generate_ssh_key_pair`, `store_ssh_key`, `delete_ssh_key`, `get_ssh_key` and `setup_authorized_keys`
- **Shell input validation (users)**: Shell path validated against `LOGIN_SHELLS` allowlist in `create_user` / `update_user`
- **`/auth/logout` response bug**: Fixed `Response(content=dict(...))` which serialised to `None`; now returns proper JSON string

---

## [0.1.0] - 2026-02-15

Initial pre-release — see [releases/0.1.0.md](releases/0.1.0.md) for full details.
