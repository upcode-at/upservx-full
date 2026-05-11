# Changelog

All notable changes to UpservX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Activity Bell in Sidebar**: New activity dropdown above the theme switcher with a larger overlay panel for operational visibility
- **Recent Status Timeline**: Activity panel now shows the latest 10 backup/replication status changes (`running`, `completed`, `failed`) with progress bars for running items
- **Backup/Replication Start Notifications**: New notification events `backup_started` and `replication_started` added to settings, defaults and dispatch logic

### Changed
- **Activity Log API output**: Log content endpoint now returns plain text by default for direct readability; JSON output remains available via explicit format selection
- **Log path handling**: Improved log file resolution to correctly support nested paths such as `upservx/activity.log`
- **CLI log rendering**: Log output is formatted for human-readable display instead of raw JSON lines when possible
- **Activity filtering**: Sidebar activity list now only displays events that are part of the notification event selection set
- **Progress labels**: Backup and replication progress/status labels introduced in this cycle are standardized to English

### Fixed
- **Activity history persistence**: The recent status list is no longer cleared on transient fetch/API errors and keeps the last known 10 entries

## [0.5.0] - 2026-05-03

> Full release notes: [releases/0.5.0.md](releases/0.5.0.md)

### Added
- **Security Module**: New dedicated security dashboard (admin-only) with five tabs — Fail2Ban, Packages, Certificates, Open Ports and CVE Scan
  - New `handlers/security.py` — business logic for all security features
  - New `api/security.py` — FastAPI router registered at `/security`
  - New `components/security.tsx` — full frontend component with tabbed UI, summary cards, filters and sort controls
- **Fail2Ban Management**: View all jails with banned IP counts, list banned IPs per jail, unban individual IPs via `fail2ban-client`
  - `POST /security/fail2ban/unban` — body: `{ "jail": "...", "ip": "..." }`
- **Package Upgrade Tracker**: List all upgradeable packages (Debian/Ubuntu), distinguish security-only updates, upgrade all or individual packages
  - `GET /security/packages` — returns upgradeable packages with current/target version and security flag
  - `POST /security/packages/upgrade` — upgrade all packages (non-interactive `apt-get upgrade -y`)
  - `POST /security/packages/upgrade/{name}` — upgrade a single package (name validated with regex to prevent injection)
- **SSL/TLS Certificate Inspector**: Scan `/etc/ssl/`, `/etc/nginx/`, `/etc/letsencrypt/`, `/etc/apache2/`, `/etc/haproxy/` for X.509 certs; shows CN, issuer, expiry date, days remaining and VALID / EXPIRING SOON / EXPIRED status; filter by status and sort by days remaining
  - `GET /security/certificates`
- **Open Port Scanner**: List all LISTEN sockets via `ss -tlnpu` with process name, PID, protocol and address; filter by TCP/UDP and by Public/Loopback address
  - `GET /security/ports`
- **CVE Vulnerability Scanner**: Batch-query installed packages against the [OSV.dev](https://osv.dev) API (`/v1/querybatch`); show CVE IDs, CVSS scores (V2/V3/V4), severity badges and advisory summaries; filter by severity
  - `GET /security/cve?limit=300` (limit range 50–1000)
- **Sidebar entry**: *Security* item added to the Administration section (requires admin group, icon: ShieldAlert)

## [0.4.0] - 2026-04-04

> Full release notes: [releases/0.4.0.md](releases/0.4.0.md)

### Added
- **VLAN Support for VMs**: Bridge-mode VM interfaces now accept an optional VLAN ID (1–4094)
  - `ensure_vlan_interface(parent, vlan_id)` creates a tagged sub-interface (e.g. `eth0.100`) on the host automatically if it does not exist
  - `vlan_id` field added to `VirtualMachine`, `VirtualMachineCreate` and `VirtualMachineUpdate` models
  - `create_vm`, `update_vm` and `import_vm_ova` pass `vlan_id` through to the host-interface setup logic
  - VLAN ID input (1–4094) added to the Create VM, Edit VM and Import VM dialogs (bridge mode only)
  - VLAN ID is stored in the VM registry and restored correctly when editing an existing VM
- **Internal VM Networks**: New `"internal"` network mode for VMs — isolated L2 libvirt networks with no DHCP, no subnet and no host routing
  - New `handlers/vm_networks.py` — `list_vm_networks`, `create_vm_network`, `delete_vm_network`, `start_vm_network`, `stop_vm_network`
  - New `api/vm_networks.py` — REST endpoints registered at `/vm-networks`
  - `network_name` field added to `VirtualMachineCreate` and `VirtualMachineUpdate`; stored as `network:<name>` in the VM registry
  - `create_vm`, `update_vm` and `import_vm_ova` handle `"internal"` mode via `--network network=<name>`
  - **Manage Networks** dialog in the VM dashboard: table of all libvirt networks with Start/Stop/Delete actions and a name-only create form
  - **Networks** toolbar button opens the dialog; shortcut link also available inside the VM create/edit dialog
  - `start_vm_network` and `stop_vm_network` are idempotent — no error if the network is already in the target state
- **New API endpoints**:
  - `GET /vm-networks` — list all defined libvirt networks (active and inactive) with details
  - `POST /vm-networks` — create a new isolated internal network (body: `{ "name": "..." }`)
  - `DELETE /vm-networks/{name}` — stop (if active) and permanently delete a network
  - `POST /vm-networks/{name}/start` — activate a network (idempotent)
  - `POST /vm-networks/{name}/stop` — deactivate a network (idempotent)
- **CLI v0.4.0**: `upservx` CLI version bumped to `0.4.0`

### Changed
- `VirtualMachineCreate.network_mode` now accepts `"internal"` in addition to `"nat"`, `"bridge"`, `"unconfigured"` and `"none"`
- `import_vm_ova` endpoint now accepts `vlan_id: int` (0 = none) and `network_name: str` (empty = none) form fields

## [0.3.0] - 2026-03-13

> Full release notes: [releases/0.3.0.md](releases/0.3.0.md)

### Added
- **VM OVA/OVF Export**: Virtual machines can now be exported as portable OVA or OVF packages
  - New `POST /vms/{name}/export` endpoint – accepts `{ "format": "ova" | "ovf" }`, converts disks from qcow2 to VMDK (`streamOptimized`) via `qemu-img` and builds a standards-compliant OVF 1.0 descriptor with CPU, RAM, network and disk mappings
  - New `GET /vms/exports/{filename}` endpoint – streams the finished archive as a file download
  - SHA-256 manifest file (`.mf`) is generated automatically and included in every export
  - OVA mode: OVF descriptor + manifest + VMDKs bundled in a single TAR archive, correct OVA member order
  - OVF mode: descriptor and VMDKs written to a named directory under `/etc/upservx/exports/`
  - VM must be stopped before export; running VMs are rejected with a clear error message
  - Export button (↓ icon) added to both Grid and List views in the Virtual Machines UI
  - Export dialog lets the user choose the format with a description of what each option does and a conversion-time warning
- **VM OVA/OVF Import**: Virtual machines can now be imported from OVA or OVF files
  - New `POST /vms/import` endpoint – accepts a multipart file upload (`.ova` or `.ovf`) plus parameters `name`, `network_mode`, `bridge_interface`, `autostart`, `storage_path`
  - OVA archives are extracted safely (path-traversal check); OVF directories are read directly
  - OVF descriptor is parsed to extract CPU count, RAM size and disk file references
  - VMDK disks are converted to qcow2 via `qemu-img convert`; source format is auto-detected via `qemu-img info`
  - VM is registered with libvirt via `virt-install --import` and added to the UpservX registry in stopped state
  - Import button added to the Virtual Machines header
  - Import dialog: file picker (`.ova`/`.ovf`), VM name (pre-filled from filename), network mode, optional bridge interface, optional storage target, autostart toggle
- **App Store Pagination**: Configurable pagination for the App Store UI
  - Page size selector with options 10, 20, 30 and 50 apps per page (default: 20)
  - Numbered page buttons with `...` ellipsis for large page counts, Prev/Next navigation
  - App count display ("X Apps gefunden") and current page indicator ("Seite X von Y")
  - Resetting to page 1 automatically when the search query, category filter or page size changes
- **App Store Templates** – 19 new pre-configured one-click applications:
  - **RustDesk** (`networking`) – Self-hosted remote desktop relay and ID server (KRaft mode, `hbbs` + `hbbr` containers)
  - **Apache Guacamole** (`networking`) – Clientless browser-based RDP/VNC/SSH gateway (guacd + web + PostgreSQL)
  - **ONLYOFFICE Community Edition** (`productivity`) – Full office suite stack: DocumentServer, CommunityServer (portal, CRM, projects), MailServer and MySQL
  - **Apache Kafka** (`other`) – Distributed event streaming platform in KRaft mode (no ZooKeeper) with Kafka UI
  - **Elasticsearch** (`other`) – Distributed search and analytics engine (v8.17.0) with Kibana, xpack security enabled
  - **Mailcow** (`other`) – Complete self-hosted mail server suite: Postfix, Dovecot, Rspamd, ClamAV, SOGo webmail, Nginx, ACME/Let's Encrypt, Netfilter, Watchdog and more (17 containers)
  - **Roundcube** (`productivity`) – Browser-based IMAP webmail client with SQLite backend and Mailcow integration guide
  - **Neo4j** (`other`) – Graph database (v5) with APOC plugin and Neo4j Browser UI (ports 7474 + 7687)
  - **RabbitMQ** (`other`) – Message broker supporting AMQP/MQTT/STOMP with Management UI (`rabbitmq:4-management`)
  - **OctoPrint** (`other`) – Web interface for 3D printers; USB serial device and webcam (mjpg-streamer) support via commented config
  - **Tunarr** (`media`) – Virtual live TV channels from Plex/Jellyfin/Emby libraries, exposed as HDHomeRun or M3U/XMLTV
  - **Loki** (`monitoring`) – Horizontally scalable log aggregation system by Grafana Labs; label-based indexing, LogQL, native Grafana integration and Promtail agent support
  - **Traefik** (`networking`) – Modern HTTP reverse proxy and load balancer with automatic Docker service discovery, Let's Encrypt SSL, built-in dashboard and middleware support (port 80/443/8080)
  - **Keycloak** (`security`) – Open-source Identity and Access Management; SSO, OIDC/OAuth 2.0/SAML 2.0, social login, user federation, 2FA — backed by PostgreSQL with healthcheck dependency
  - **Harbor** (`development`) – Enterprise container image registry with RBAC, vulnerability scanning (Trivy), content signing, replication and multi-tenancy; full multi-service stack (core, portal, jobservice, registry, registryctl, db, redis, nginx) at v2.11.0
  - **GitLab** (`development`) – Complete DevSecOps platform: Git repositories, CI/CD pipelines, container registry, issue tracking, wikis and OIDC/LDAP auth; Omnibus single-container setup with Puma/Sidekiq memory tuning
  - **OpenLDAP** (`security`) – Centralised LDAP directory for user and group management; Bitnami image with phpLDAPadmin web UI (port 8090); integration guides for Keycloak, GitLab and Grafana
  - **Docker Registry** (`development`) – Lightweight private container image registry (Registry v2) with Docker Registry UI (port 8085, joxit); optional htpasswd basic auth and Traefik reverse-proxy support
  - **MotionEye** (`monitoring`) – Web frontend for the motion daemon; supports USB cameras, IP/RTSP/MJPEG streams, motion-triggered recording, snapshots, notifications and timeline view (port 8765)
- **Group-based Access Control (RBAC via Linux groups)**: New `permissions.py` module maps Linux groups to subsystem access — authenticated users only see and can access what their groups permit
  - `sudo` / `wheel` → full administrator access (all endpoints)
  - `docker` → container management (Docker), Docker images, App Store
  - `lxd` / `lxc` → container management (LXC), LXC images
  - `libvirt` / `kvm` → virtual machine management, ISO management
  - `disk` / `storage` → physical storage management (`/drives/*`)
  - `tty` → system shell access (`/system/shell`)
  - `adm` / `log` → log viewer access (`/logs`, `/activity-log`)
  - API keys and cluster tokens receive implicit full-admin rights
- **`GET /auth/me`** endpoint: returns the authenticated user's username, resolved Linux groups and a `permissions` object (`admin`, `containers`, `vms`, `storage`, `shell`, `logs`) — used by the frontend to build the permission-aware sidebar
- **`GET /info`** endpoint: public (but authenticated) endpoint returning the server hostname — used by the sidebar so non-admin users can see the hostname without requiring `/settings` access
- **Session-cookie authentication**: login now issues an `HttpOnly` `SameSite=Lax` cookie via `POST /auth/login`; `localStorage` token storage removed entirely
  - `fetch` interceptor in `AuthProvider` forwards `credentials: "include"` on every request instead of injecting `Authorization` headers
  - `POST /auth/logout` deletes the cookie server-side
  - Session validity is verified on page load via `/auth/me` + cookie; `isLoaded` is only set to `true` after permissions are resolved (prevents sidebar flash)
- **Application Customization Module**: New "Customization" tab in Settings (visible to admins only) to personalize the login screen and dashboard branding
  - **Login Banner Text**: Configurable title and subtitle displayed on the left side of the login page
  - **Custom Logo**: Upload a PNG, JPG, SVG, GIF or WebP logo — replaces the default logo on both the login screen and the sidebar in the dashboard
  - **Custom Banner Image**: Upload a background image for the left panel of the login screen
  - Image previews shown directly in the settings UI; existing files can be removed to revert to defaults
  - Customization files stored in `/etc/upservx/customization/`, text config in `/etc/upservx/customization/config.json`
  - **Login page** dynamically loads banner title, subtitle, logo and background image from the API at render time — falls back silently to defaults if the API is unreachable
  - **Sidebar logo** dynamically loads the custom logo when one is uploaded; falls back to `logo.png` / `logo_light.png` depending on theme
  - All `GET` customization endpoints (`/settings/customization`, `/settings/customization/logo/file`, `/settings/customization/banner/file`) are public (no authentication required) so the login screen can fetch them before a session exists
  - Write/delete operations remain auth-protected and are restricted to admin users in the UI
  - API routes: `GET /settings/customization`, `POST /settings/customization`, `POST /settings/customization/logo`, `DELETE /settings/customization/logo`, `GET /settings/customization/logo/file`, `POST /settings/customization/banner`, `DELETE /settings/customization/banner`, `GET /settings/customization/banner/file`

### Changed
- **Auth middleware**: after successful PAM / API-key authentication, the middleware now resolves the user's Linux groups and calls `check_path_permission()` — returns HTTP 403 for paths the user's groups do not cover
- **System shell WebSocket**: access guard changed from `is_admin()` to `has_shell_access()` — `tty` group members may now open the shell in addition to `sudo`/`wheel`; unauthorised connections are closed with WebSocket code `4403`
- **Sidebar**: each navigation item now carries a `requires` field (`"admin"`, `"containers"`, `"vms"`, `"storage"`, `"shell"`, `"logs"` or `null`); items and entire categories are hidden when the logged-in user lacks the required permission — no client-side workarounds needed
- **`AuthContext`**: extended with `username`, `groups[]`, `permissions` and `reloadPermissions()` — `useAuth()` consumers can read current permissions without additional fetches; `token` kept as compatibility shim (`"__session__"` when authenticated, `null` otherwise)
- **`getAuthHeaders()` / `getJsonHeaders()`** in `api.ts`: removed the `admin:admin` Basic-auth fallback; auth is now handled exclusively via session cookie
- **Frontend layout/theme polish**: moved the theme switch to the sidebar (with Light/Dark/System modes), removed the now-empty top header, simplified logout button to an icon, improved light-mode tab/button contrast, and removed the active-item white dot in the sidebar

### Security
- **Group-based authorisation**: every API request is now checked against the caller's Linux groups — users without the appropriate group receive HTTP 403 instead of having unrestricted access to all endpoints
- **Removed `admin:admin` fallback**: `api.ts` no longer falls back to hardcoded credentials when no session exists
- **HttpOnly session cookie**: the auth token is no longer stored in `localStorage` (accessible to JavaScript); the `HttpOnly` flag prevents client-side script access to the session cookie

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
