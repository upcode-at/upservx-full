## Release v0.6.0 - Cluster HA & UX Improvements

**Release Date:** 2026-06-06

### What's New in UpservX v0.6.0

This release focuses on cluster reliability and usability. High Availability coordination has been tightened across nodes, child nodes now see the full cluster state from the master, and the cluster management UI was aligned with the rest of the application for a more consistent full-width tab layout.

---

### Highlights

#### High Availability Improvements

- **Cross-node VIP ownership propagation**
  - New inter-node endpoint `POST /cluster/ha/vip-owner-update` distributes the active VIP owner state across the cluster
  - Cluster status now exposes `vip_owner_hostname`, `vip_owner_ip` and the active HA interface for better diagnostics

- **Safer VIP placement**
  - VIPs are now assigned directly on the configured physical interface instead of a dedicated dummy interface
  - This avoids routing inconsistencies and LAN reachability issues during failover

- **Local HA config boundaries**
  - Node-local HA settings are no longer synchronized between nodes
  - `GET /cluster/ha/config` now only returns shareable HA settings for cluster sync

#### Cluster Visibility & Management

- **Full cluster view on child nodes**
  - Child nodes now load the complete cluster view from the master instead of building a reduced local view
  - Secondary nodes now display the same membership list as the master

- **More robust node removal**
  - Node removal now resolves targets reliably by stored hostname, original hostname, assigned hostname or IP address
  - Force-leave cleanup is now best-effort and non-blocking when a child node is offline

#### UI Consistency

- **HA settings safeguards**
  - HA configuration inputs are locked while HA is enabled to prevent live edits of active failover settings

- **Cluster UI polish**
  - Remaining HA and cluster-adjacent labels were standardized to English
  - Cluster module tabs now span the full page width like the other administration modules

---

### Upgrade Notes

- No database migration required for this release.
- Review local HA interface and VIP settings after upgrading if you previously relied on dummy-interface based VIP placement.
- No additional dependency installation steps are required beyond the usual application update process.
