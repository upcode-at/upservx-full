# TODO – UpservX

This file contains only work that is still open based on the current
repository state. Concrete defects, security gaps, and missing quality gates
take precedence over general ideas.

**Last full repository audit:** August 5, 2026

**Audited version:** `0.6.0`

**Priorities:** P0 = release blocker, P1 = required before stable production
use, P2 = next feature phase, P3 = long-term/enterprise roadmap

## P0 – Release blockers

### Authorization and trust boundaries

- [x] Correct backend authorization comprehensively and cover it with negative
  tests.
  - `/security/*` and user-facing `/cluster/*` and `/cluster/ha/*` operations
    now require administrator access; `/vm-networks/*` requires a VM role.
  - Every registered route is classified by HTTP method and read/write action
    instead of inheriting access from a URL prefix.
  - Cluster principals are no longer administrators and are limited to the
    explicit inter-node and inventory routes required for cluster operation.
  - Negative tests cover every Linux role, API keys, cluster principals,
    cross-subsystem access, wrong methods, and unknown routes. Unknown routes
    are denied even for administrators and API keys.

- [x] Harden authentication for internal cluster and HA endpoints.
  - Inter-node requests are HMAC-SHA256 signed over their exact method, target,
    body digest, node identity, key ID, timestamp, and nonce. Unknown peers,
    expired timestamps, malformed signatures, and replayed nonces fail closed.
  - Cluster traffic uses the dedicated HTTPS listener on port 9501. Peer CAs
    are authenticated during nonce-bound bootstrap and pinned; signed requests
    are rejected on the unencrypted public listener.
  - Key rotation distributes a pending key to every peer before commit and
    retains the previous key only for a bounded overlap period.
  - `/cluster/info` no longer contains the cluster token. The create and rotate
    operations return their new enrollment token only in the mutation response.

- [x] Harden secrets and sessions.
  - Backup and encryption diagnostics no longer print credential objects,
    encryption-key previews, or ciphertext previews. Backup, notification,
    TOTP, and general secret encryption now raise on failure instead of
    storing or returning plaintext.
  - Pending 2FA login records contain only a hashed random token, username,
    first-factor timestamp, expiry, and attempt count. Startup migration
    removes password fields from legacy records.
  - User sessions are signed, expiring, and backed by hashed server-side
    records for immediate logout, password-change, and security-change
    revocation. Browser cookies default to `Secure`, `HttpOnly`,
    `SameSite=Strict`, `Path=/`, and explicit `Max-Age`/expiry attributes.
  - The global plaintext API key has been replaced with hashed, individually
    revocable API tokens with roles, scopes, and optional expiry. Legacy keys
    migrate into revocable hashed records and are removed from `settings.json`.
  - One central storage policy atomically writes configuration files as `0600`,
    creates directories as `0700`, rejects symlinks, and repairs the complete
    `/etc/upservx` tree at startup. Regression tests cover every behavior above.

### Process model and persistent state

- [x] Correct the backend process model used with `uvicorn --workers 4`.
  - The browser-facing Uvicorn server is explicitly single-process. This keeps
    rate limits, WebSocket tickets, metric state, and singleton managers
    consistent until those components are moved to external stores.
  - The separate TLS listener is signed-cluster-only and passive: it cannot
    accept browser sessions or API tokens and does not start a second HA loop.
  - TOTP, HA, replication configuration, backup configuration, and legacy
    progress JSON updates use cross-process file locks and atomic replacement.
    Corrupt security-sensitive state fails closed.

- [x] Move long-running work out of HTTP and worker processes.
  - A dedicated systemd worker claims jobs transactionally from an owner-only
    SQLite WAL database. Backups, replications, VM and cluster exports, package
    and CVE scans, package upgrades, and system updates all use this queue.
  - Jobs expose durable status, progress, results, checkpoints, attempts,
    exponential retry, cancellation, manual retry, and per-kind hard timeouts.
    Task subprocess groups are terminated on cancellation or timeout.
  - A singleton worker lock prevents competing supervisors. On restart, its
    recovery transaction requeues interrupted work with its checkpoint (or
    finalizes cancellation/failure), so no job remains permanently `running`.

### Installation, service privileges, and updates

- [x] Define and install one unambiguous privilege model.
  - The API and worker run as the dedicated `upservx` system account; the
    separately sandboxed frontend runs as `upservx-web`. Immutable releases
    are root-owned and mutable state, configuration, logs, and runtime files
    have explicit owners and modes.
  - A root-owned helper is the only sudoers entry. It validates named host
    operations and arguments; backend-only command shims route networking,
    firewall, account, storage, package, certificate, and systemd operations
    through it. Settings, fstab, cron, SSH-key, VPN, and nginx writes use
    dedicated helper actions.
  - Docker, LXD, and libvirt/KVM groups are added only for selected profiles.
    The installed smoke test audits identities, groups, sudo policy, the full
    `/etc/upservx` ownership/mode policy, units, HTTPS, noVNC, and readiness.

- [x] Rebuild the update path.
  - Releases are versioned, signed artifacts rather than Git checkouts. The
    root-owned `upservx-update@VERSION.service` runs independently of the API,
    verifies SHA-256 plus the detached signature, and rejects unsafe archive
    paths, links, permissions, ownership, or missing release content.
  - The updater backs up `/etc/upservx`, builds an immutable release, switches
    `/opt/upservx/current` atomically, restarts and probes the public services,
    and restores the previous release when readiness fails. Deployment assets
    are validated before installation.
  - Persistent jobs monitor root-owned updater state. Cancellation stops the
    external unit, worker processes restart onto the new release after their
    active job ends, and every non-zero exit is returned as a failed job.

- [x] Make the installer safe and minimal.
  - PAM is never edited. Core installation is separate from container,
    virtualization, cluster, database, FTP, VPN, and ZFS profiles.
  - NodeSource and Docker repository keys and the K3s/kubectl downloads require
    caller-supplied SHA-256 pins; missing pins fail closed.
  - Frontend dependencies use `npm ci`; backend and CLI environments install
    exact, complete lock files. The frontend, API, and worker have separate
    units, loopback application listeners, an HTTPS nginx entry point, startup
    readiness probes, and recurring liveness recovery.

- [x] Repair the noVNC source in the repository.
  - The existing pinned Gitlink now has an explicit `.gitmodules` mapping to
    the official `https://github.com/novnc/noVNC.git` repository. Installation
    verifies that the populated submodule matches the pinned Gitlink, and
    signed release artifacts carry that exact source.

### Make the backup system functional

- [x] Use one data source for backup servers.
  - SQLite now owns CRUD, jobs, encrypted credentials, and foreign keys.
  - Legacy `backup_servers.json` data is imported once and archived.
  - Server connection states are `connected`, `disconnected`, or `error`.

- [x] Make scheduled backups executable.
  - Cron uses the installed interpreter and `handlers/execute_backup.py`.
  - Schedule/status changes atomically replace or remove existing entries.
  - Cron, manual, CLI, and UI runs share the durable worker queue path.

- [x] Complete the backup lifecycle.
  - Safe staged restore workflows reject traversal, links, special files, and
    implicit overwrites for file, container, and VM archive assets.
  - Deletion and retention remove the local/SFTP archive before metadata.
  - Production honors compression and performs checksums, verification, and
    test restores, including post-upload remote verification.
  - Running VMs use quiesced atomic libvirt snapshots through QEMU Guest Agent.

### Broken API contracts and cluster synchronization

- [x] Align the frontend, CLI, and backend with a shared API contract.
  - Backup-server info, SSH-key, container restart, and container inspect routes
    now match their clients.
  - CLI backup creation sends `BackupJobCreate`, and CLI login completes 2FA.
  - TypeScript/CLI request types and contract tests derive from OpenAPI.

- [x] Finish container synchronization in the cluster or remove it from the UI
  until it works.
  - Unsafe replication/migration controls are removed from the UI.
  - Mutation/execute endpoints return `501` and never report false success until
    volumes, secrets, networks, ports, images, source stop, and rollback can be
    handled transactionally.

### Correct the App Store

- [ ] Make every template pass mandatory schema and Compose validation.
  - `mailcow/docker-compose.yml` is syntactically invalid.
  - `apache-kafka/` is empty even though Kafka is listed as available in the
    release notes.
  - Home Assistant, Paperless-ngx, and Uptime Kuma use object arrays for
    `ports`, `volumes`, and `environment`; the current frontend expects
    `string[]` or a string-valued object and cannot render the detail view
    reliably.
  - Define a JSON schema and migrate all 61 complete existing templates to it.

- [ ] Turn “Install” into a real, secure installation.
  - The handler currently only copies the template into a project directory and
    does not start a Compose stack.
  - Make environment variables from `app.json` editable in the installation
    dialog, validate required fields, and generate secrets securely.
  - Remove hard-coded default passwords and `changeme`/`admin` credentials
    from production Compose files.
  - Execute installation transactionally: validate Compose, pull images, start
    services, wait for health checks, and roll back on failure.
  - Correctly associate custom project names with installation status.
  - Pin image versions intentionally and define a tested application update
    path instead of using uncontrolled `latest` tags everywhere.

### Restore mandatory quality gates

- [ ] Repair the frontend lint command for Next.js 16.
  - `npm run lint` uses the removed `next lint`; invoking ESLint directly
    works.
  - Align the `eslint-config-next` major version with `next`.

- [ ] Configure CI checks as real gates.
  - Backend tests and both linters must no longer swallow errors through
    `continue-on-error` or `|| echo`.
  - Apply Python syntax checks recursively to `api/`, `handlers/`, `lib/`,
    the CLI, and tests instead of only `*.py` in the root directory.
  - Add App JSON schema checks, `docker compose config`, shell syntax,
    OpenAPI contracts, the frontend build, and CLI tests to CI.
  - Provide a documented, reproducible test command for local development; the
    root `.venv` in the current checkout contains neither pip nor an
    importable pytest installation.

## P1 – Stability before production use

### Tests and real integrations

- [ ] Expand backend test coverage to all critical modules: backup, cluster/HA,
  VM/LXC/KVM, App Store/Compose, firewall, networking, reverse proxy, security,
  settings/VPN, notifications, and updates.
- [ ] Update stale tests to use Bearer/cookie authentication; fixtures still
  document Basic Auth even though the middleware accepts only Bearer tokens.
- [ ] Add real system tests in isolated VMs:
  - Fresh installation and updates on supported Debian and Ubuntu versions
  - Docker and Compose, LXD/LXC, KVM/libvirt, and noVNC
  - Backup and restore locally and over SSH
  - Two- and three-node clusters, including network failure and split-brain
  - Firewall, network, and disk operations with safe rollback
- [ ] Add frontend component, accessibility, and end-to-end tests.
- [ ] Add CLI unit and contract tests for every documented command.

### Input, resources, and error handling

- [ ] Stream and limit uploads and downloads.
  - ISO upload, VPN/logo/banner upload, and cluster upload partly lack size
    limits and read entire files into memory.
  - Cluster export uses `capture_output` for complete container and image
    archives; large resources must stream directly to disk or storage.
  - Add quotas, free-space checks, timeouts, cancellation, and cleanup of
    incomplete files.
- [ ] Harden ISO URL downloads against DNS rebinding, redirects, IPv6/private
  networks, missing timeouts, and unlimited file sizes.
- [ ] Validate image uploads by their actual contents, either sanitize or
  prohibit SVG, and serve stored files with secure headers.
- [ ] Validate destructive operations on the server: the system disk, root
  filesystem, active network interface, management access, and unrelated paths
  must not be accidentally formatted, unmounted, or disconnected.
- [ ] Replace broad `except Exception`/`pass` blocks with defined errors,
  structured logs, and actionable API errors.
- [ ] Remove debug output from backup and cluster code and use consistent,
  redacted logging with rotation and audit events.

### Frontend and usability

- [ ] Replace the global `window.fetch` monkey patch with a central API client
  that handles cookies, errors, timeouts, cancellation, and 401 responses
  consistently.
- [ ] Implement loading, empty, partial-failure, and retry states consistently
  across all modules; do not discard errors only to the browser console.
- [x] Expose backups, replications, exports, scans, and updates through
  persistent job progress instead of blocking requests. The affected frontend
  flows poll durable status and surface completion or failure.
- [ ] Require confirmation for security-critical actions that explains the
  exact impact, target, and recoverability.
- [ ] Remove the hard-coded development IP from `next.config.ts` and make
  allowed origins configurable.

### Data models and maintainability

- [ ] Consolidate persistence. SQLite, numerous JSON files, `/etc/crontab`,
  and process memory are currently used in parallel, resulting in inconsistent
  transactions, migrations, backups, and ownership.
- [ ] Remove unused or contradictory database dependencies and documentation
  claims about PostgreSQL/SQLAlchemy/Alembic, or implement real, versioned
  database migrations.
- [ ] Split large modules (`api/cluster.py`, `handlers/vms.py`, and several
  very large React components) into clearly tested domains.
- [ ] Use Pydantic v2 APIs (`model_dump`) consistently and define input models
  with enums, limits, path/name validation, and meaningful constraints.
- [ ] Regularly and transparently clean up background state, temporary exports,
  uploads, and stale progress data.

### Documentation and repository hygiene

- [ ] Synchronize documentation with the actual code.
  - Authentication documentation still partly describes Basic Auth and Base64
    cookies.
  - Many endpoint tables, file paths, model names, and function names do not
    match the registered routers.
  - The architecture claims PostgreSQL/Alembic and an old file structure,
    although the active code primarily uses JSON and SQLite.
  - App Store documentation lists 49 apps; there are 61 complete templates plus
    an empty Kafka directory.
  - `upservx/README.md` is still the generic Create Next App README.
- [ ] Define supported versions unambiguously.
  - Because it uses `X | None`, the code requires at least Python 3.10, while
    the README and documentation promise Python 3.8.
  - The installer and CI use Node 20, while the README names Node 18; the
    Next.js version in the badge is also incorrect.
- [ ] Extend `.gitignore` for local virtual environments, runtime key
  directories, test/build caches, and temporary backend data.
- [ ] Convert debug/helper scripts (`debug_backup_test.py`,
  `test_encryption.py`) into real tests or remove them from the product source
  tree.

## P2 – Next feature phase

### Virtual machines

- [ ] Implement managed VM templates and versioned images with fast rollout.
- [ ] Support linked clones in addition to the existing full clone.
- [ ] Add multiple network interfaces per VM, per-VM port forwarding, and
  firewall/security profiles.
- [ ] Integrate QEMU Guest Agent: IP/hostname detection, orderly shutdown,
  filesystem freeze/thaw, and backup-consistent snapshots.
- [ ] Manage libvirt storage pools as a dedicated model with capacity,
  selection, permissions, and lifecycle.
- [ ] Test existing cloud-init, snapshots, cloning, and OVA/OVF import/export
  interoperability with different distributions, firmware types, multi-disk
  VMs, and external hypervisors.

### Backup and disaster recovery

- [ ] Optionally encrypt backup archives client-side or before upload; support
  key rotation, recovery keys, and documented recovery.
- [ ] Implement incremental/deduplicated backups, bandwidth limits, and
  resumable remote transfers.
- [ ] Support retention rules based on count, age, and storage budget, as well
  as immutable and off-site targets.
- [ ] Document and automatically test a complete disaster recovery procedure
  for UpservX configuration, users, clusters, apps, containers, and VMs.

### Networking, storage, and platform

- [ ] Add bonding, managed bridges, Open vSwitch, and VXLAN/overlay networks.
- [ ] Integrate NFS/iSCSI and LVM Thin as first-class storage pools.
- [ ] Clearly separate load-balancing capabilities:
  - Reliably execute existing workload placement and recommendations.
  - Optionally provide an HAProxy/Traefik data store, health checks, TLS, and
    sticky sessions as a real traffic load balancer.
- [ ] Add resource pools, quotas, placement/anti-affinity rules, and scheduled
  maintenance modes.

### Identities and UX

- [ ] Integrate LDAP/Active Directory and OIDC/SAML SSO, and map external groups
  to internal roles.
- [ ] Model roles more precisely than Linux groups: read-only, operator,
  subsystem admin, and audit-only.
- [ ] Introduce the technical foundation for internationalization, then provide
  complete English and German translations; add more languages only on the
  same translation foundation.
- [ ] Systematically audit keyboard operation, screen reader text, focus
  management, contrast, and responsive presentation against WCAG.
- [ ] Add a complete audit history for user, API, and cluster actions with
  filtering, export, and tamper-resistant retention.

## P3 – Long-term enterprise roadmap

- [ ] Build a quorum-based cluster with fencing/STONITH and demonstrable
  split-brain protection; first clearly mark the existing custom HA logic as
  experimental.
- [ ] Support live migration of running VMs, including shared and local storage
  handling.
- [ ] Integrate Ceph/RBD, storage replication, and optional erasure coding.
- [ ] Implement automatic HA resource recovery, startup ordering, failover
  policies, and maintenance orchestration.
- [ ] Develop multi-node upgrades with version compatibility checks, staged
  rollout, and automatic rollback.
- [ ] Evaluate multi-tenancy with isolated resources, networks, secrets,
  billing/quotas, and delegated administration.

## Definition of done for the next release candidate

- [ ] A clean clone has no broken Gitlink and builds reproducibly.
- [ ] `npm ci`, the frontend build, ESLint, Python linting, all backend/CLI
  tests, contract tests, and all template validators pass locally and in CI
  without ignored errors.
- [ ] Installation and update, including rollback, have been tested on at least
  one supported Debian version and one supported Ubuntu version.
- [ ] No route with system-changing privileges is accessible to an unauthorized
  role; internal cluster endpoints are authenticated and encrypted.
- [ ] A backup has been created, verified, restored, and removed by its
  retention rule both locally and over SSH.
- [ ] App Store installation starts a validated stack without known default
  passwords and reports health and rollback status correctly.
- [ ] Documented APIs, CLI commands, versions, paths, and prerequisites match
  the shipped code.

## Already implemented – do not plan again as missing

The following items from the old TODO already exist at a basic level in the
current code and need testing or hardening rather than reimplementation:

- Cloud-init user data during VM creation
- VLAN support and internal libvirt networks
- VM cloning, snapshots, and OVA/OVF import and export
- Linux-group permissions, revocable scoped API tokens, sessions, and TOTP 2FA
- Basic cluster, replication, placement, and HA/VIP interfaces
- Basic local and SSH-based backup functionality
- nftables firewall, reverse proxy, certificates, VPN, and security dashboard
