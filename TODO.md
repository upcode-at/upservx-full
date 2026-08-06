# TODO – UpservX

This file contains only work that is still open based on the current
repository state. Concrete defects, security gaps, and missing quality gates
take precedence over general ideas.

**Last full repository audit:** August 5, 2026

**Release target:** `0.7.0`

**Priorities:** P0 = release blocker, P1 = required before stable production
use, P2 = next feature phase, P3 = long-term/enterprise roadmap

## P0 – Release blockers

### COMPLETED

## P1 – Stability before production use

### Tests and real integrations

- [ ] Expand backend test coverage to all critical modules: backup, cluster/HA,
  VM/LXC/KVM, App Store/Compose, firewall, networking, reverse proxy, security,
  settings/VPN, notifications, and updates.
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
