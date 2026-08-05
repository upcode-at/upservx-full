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

- [ ] Correct backend authorization comprehensively and cover it with negative
  tests.
  - `/security/*` is not currently classified as an admin area. As a result,
    any authenticated user can trigger package upgrades and remove Fail2Ban
    bans, among other actions.
  - `/cluster/*`, `/cluster/ha/*`, and `/vm-networks/*` also fall through
    the current default allow behavior. Cluster creation, replication,
    failover, and network changes must require explicit roles.
  - Define permissions per route and action instead of relying only on URL
    prefixes; handle read and mutation operations separately.
  - Add tests for every role, API keys, cluster principals, and unknown routes.
    The default behavior must be deny by default.

- [ ] Properly authenticate internal cluster and HA endpoints.
  - The middleware skips heartbeat, vote, master-update, VIP-owner-update, and
    config-sync requests; the routes themselves currently do not verify a
    cluster key.
  - Sign messages or use mTLS, add replay protection and time windows, and
    support key rotation.
  - Stop exposing the cluster token through `/cluster/info` to every
    authenticated user.
  - Do not send inter-node traffic unencrypted over `http://`.

- [ ] Harden secrets and sessions.
  - Backup configuration must not log passwords through debug output; remove
    previews of encryption keys and ciphertext.
  - Encryption must fail closed. Never store or return plaintext as a silent
    fallback.
  - Stop storing Linux passwords temporarily in
    `/etc/upservx/login_tokens.json` during 2FA login; the username and a
    successfully completed first authentication step are sufficient.
  - Configure the session cookie for HTTPS with `Secure`, suitable
    `SameSite`/domain/path behavior, and a clear expiry and revocation
    strategy.
  - Replace the single global API key with revocable, hashed API tokens bound to
    roles and scopes.
  - Centrally define and test file permissions for all files under
    `/etc/upservx`.

### Process model and persistent state

- [ ] Correct the backend process model used with `uvicorn --workers 4`.
  - Rate limits, WebSocket tickets, the HA manager, metric state, and several
    global managers currently live only in one worker's memory.
  - A ticket can therefore be created in worker A and rejected in worker B;
    rate limits can be bypassed on a per-worker basis.
  - Either enforce a single worker for now or move all shared state into a
    transactional, concurrency-safe store.
  - Replace process-local locks around shared JSON files with real
    cross-process synchronization and atomic updates.

- [ ] Move long-running work out of HTTP and worker processes.
  - Run backups, replications, exports, scans, and updates as persistent jobs
    with status, retry, cancellation, timeout, and resume support.
  - A restart must not silently lose active work or leave it permanently marked
    as `running`.

### Installation, service privileges, and updates

- [ ] Define and install one unambiguous privilege model.
  - Depending on how it was installed, the systemd service runs either as a
    regular user or as root, while backend functions need to modify `/etc`,
    networking, the firewall, users, disks, libvirt, Docker, and systemd.
  - Create a dedicated service user and narrowly scoped privileged helpers,
    groups, or sudoers rules.
  - Configure Docker, LXD, libvirt/KVM, and file permissions reproducibly
    during installation and verify them with a post-install smoke test.

- [ ] Rebuild the update path.
  - `install.sh` copies the application to `/opt/upservx` without `.git`,
    but `update.sh` tries to run `git pull` there.
  - The update is started by the running service and stops that same service;
    with the usual systemd KillMode, this can terminate the update process
    itself.
  - Execute updates outside the web service, use signed and versioned artifacts,
    back up configuration, switch atomically, and add health checks and
    rollback.
  - Report non-zero exit codes as failures; the API currently responds with
    “update completed” even when the script fails.

- [ ] Make the installer safe and minimal.
  - Stop removing `pam_lastlog.so` globally from PAM files.
  - Require verification of downloaded K3s/repository scripts and keys; do not
    execute unverified remote scripts.
  - Install K3s, LXD, PostgreSQL, FTP/vsftpd, OpenVPN, ZFS, and other large
    components as optional profiles instead of mandatory packages.
  - Use `npm ci` and reproducibly locked Python dependencies instead of
    mutable installations.
  - Run the frontend and backend as separate systemd units with readiness and
    liveness checks.

- [ ] Repair the noVNC source in the repository.
  - `upservx/public/novnc` is a Gitlink, but no matching `.gitmodules`
    mapping exists.
  - Either add a correct submodule or obtain noVNC exclusively as an installed,
    verified dependency and remove the Gitlink.

### Make the backup system functional

- [ ] Use one data source for backup servers.
  - Create, list, and delete currently use `backup_servers.json`; update and
    connection testing use the SQLite `backup_servers` table.
  - Select one schema, migrate existing data, and use it consistently for CRUD,
    jobs, credentials, and foreign keys.
  - Standardize status values and models (`active` versus
    `connected`/`disconnected`/`error`).

- [ ] Make scheduled backups executable.
  - The cron manager points to `lib/execute_backup.py`, but the file is under
    `handlers/execute_backup.py`.
  - Cron uses `/usr/bin/python3` instead of the installed UpservX virtual
    environment.
  - Schedule and active-state changes must update or remove existing cron
    entries.
  - Cron execution, manual execution, and UI triggers must use the same tested
    code path.

- [ ] Complete the backup lifecycle.
  - Implement restore operations for file, container, and VM backups as safe
    API and UI workflows; protect tar extraction against traversal, symlinks,
    and overwrites.
  - When deleting a backup instance, also handle the local or remote archive;
    currently only the database record is deleted.
  - Apply `retention_days` to archives and metadata.
  - Respect the `compression` setting in the production execution path.
  - Add checksums, automatic integrity verification, and regular test restores.
  - Ensure VM consistency through libvirt snapshots/QEMU Guest Agent instead of
    merely suspending and archiving large active disks with tar.

### Broken API contracts and cluster synchronization

- [ ] Align the frontend, CLI, and backend with a shared API contract.
  - The frontend calls `/settings/generate-api-key`, while the backend exposes
    `/settings/api-key`.
  - The TypeScript client includes `/backup/servers/{id}/info` and complete
    `/ssh-keys/*` APIs for which no routes are registered.
  - The CLI offers container `restart` and `inspect`, although the
    corresponding backend routes do not exist.
  - `upservx backup create` does not send a valid `BackupJobCreate` object
    and therefore cannot create a job.
  - Implement CLI 2FA login or clearly mark it as unsupported.
  - Use OpenAPI as the source for generated TypeScript/CLI types and contract
    tests.

- [ ] Finish container synchronization in the cluster or remove it from the UI
  until it works.
  - The sync manager sends data to `/containers/deploy`; this route does not
    exist.
  - Reading service configuration is explicitly implemented as a placeholder.
  - “Migration” only deletes local sync state and does not stop the source
    container.
  - Partial failures are not aggregated; `/cluster/sync/execute` can report
    success even though no replication worked.
  - Correctly transfer or handle volumes, secrets, networks, port conflicts,
    images, and rollback.

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
- [ ] Expose long-running operations through job progress instead of blocking
  requests.
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
- Basic Linux-group-based permissions, API key, and TOTP 2FA
- Basic cluster, replication, placement, and HA/VIP interfaces
- Basic local and SSH-based backup functionality
- nftables firewall, reverse proxy, certificates, VPN, and security dashboard
