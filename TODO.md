# TODO - UpservX Development Roadmap

This file tracks ongoing work, planned features, and areas where contributors can help.

## 🚨 High Priority

### Virtual Machines (VMs)
**Status:** Partially implemented, needs testing and completion

The VM management feature exists but requires thorough testing and completion:

- [ ] **Complete VM Features**
  - [ ] VM Migration between hosts
  - [ ] VM Templates for quick deployment
  - [ ] Cloud-init integration for automated setup

- [ ] **VM Networking**
  - Port forwarding rules
  - VLAN support
  - Multiple network interfaces per VM

- [ ] **Storage Management**
  - Storage pool management

- [ ] **VM Import/Export**
  - Export VMs as OVA/OVF
  - Import existing VMs
  - Backup and restore VMs

## ⚖️ Enterprise Parity (Missing Advanced Features)

This list summarizes major enterprise-grade virtualization, storage, and cluster features that are currently missing or only rudimentarily implemented in the project.

- [ ] **Cluster & High Availability (HA)**
  - distributed cluster with quorum (Corosync) and automatic failover
  - fencing, HA manager and resource recovery
- [ ] **Live Migration**
  - seamless live migration of running VMs between nodes (including storage handling)
- [ ] **Enterprise Storage Integrations**
  - Ceph/RBD integration, LVM-Thin, iSCSI/NFS as first-class storage pools
  - storage pools management, replication and erasure-coding support
- [ ] **VM- and Storage-level Snapshots**
  - consistent VM snapshots (create / restore / delete)
  - native storage snapshots (ZFS, Ceph)
- [ ] **Incremental & Optimized Backups**
  - incremental/deduplicated backups, scheduling and retention policies
  - integrated restore workflows and verification mechanisms
- [ ] **RBAC & Authentication Integrations**
  - fine-grained roles, LDAP/AD/SSO integration, API token management
- [ ] **Storage Replication & Volume-level Replication**
  - asynchronous/synchronous replication of VM disks across nodes
- [ ] **Resource Pools, Scheduler & HA Policies**
  - resource pools, placement rules, anti-affinity and failover/start policies
- [ ] **Network Enterprise Features**
  - VLAN, bonding, Open vSwitch, VXLAN/overlay networks, advanced bridge tooling
- [ ] **Per-VM Firewall / Security Profiles**
  - per-VM/LXC firewall rules, zones and security profiles
- [ ] **Templates & Linked Clones**
  - managed VM/LXC templates, fast cloning and linked clones
- [ ] **Guest Agent Integration**
  - qemu-guest-agent support for quiesce, IP/hostname reporting and graceful shutdown
- [ ] **GUI: Cluster & Task Management**
  - multi-node GUI, task queue, audit logs and job history
- [ ] **Backup Repository Management & Pruning**
  - manage external repositories (NAS, S3), automated pruning/retention
- [ ] **Auditing & Monitoring**
  - centralized audit logs, detailed task history and notifications


## 🔧 Medium Priority

### Firewall Enhancements

- [ ] **Docker Integration**
  - Manage DOCKER-USER chain
  - Block/Allow specific container ports
  - Container-specific firewall rules

- [ ] **UI Improvements**
  - Rule reordering (drag & drop)
  - Rule groups/categories
  - Rule search and filtering
  - Bulk operations

### Backup System

- [ ] **Cloud Storage Integration**
  - AWS S3 support
  - Backblaze B2 support
  - Google Cloud Storage
  - Azure Blob Storage

- [ ] **Backup Encryption**
  - Encrypt backups at rest
  - Key management
  - Encrypted remote transfers

- [ ] **Backup Verification**
  - Automatic backup integrity checks
  - Restore testing
  - Backup health monitoring

## 📦 App Store

- [ ] **New App Templates Needed**
  - [ ] Heimdall
  - [ ] Traefik
  - [ ] Zigbee2MQTT
  - [ ] PhotoPrism
  - [ ] Calibre-Web
  - [ ] Seafile
  - [ ] Authentik

- [ ] **App Store Features**
  - One-click updates
  - App dependency management

## 🌐 Networking

- [ ] **Load Balancer**
  - HAProxy integration
  - Health check configuration
  - SSL termination
  - Sticky sessions

## 👥 User Management

- [ ] **Authentication**
  - 2FA/TOTP support
  - LDAP/Active Directory integration
  - OAuth2/OIDC support
  - API key management

## 🎨 UI/UX Improvements

- [ ] **Internationalization**
  - German translation
  - English (complete)
  - Spanish
  - French
  - More languages...

## 🧪 Testing & Quality

- [ ] **Unit Tests**
  - Backend API tests
  - Frontend component tests
  - Integration tests

## 🔒 Security

- [ ] **Security Hardening**
  - Security headers
  - CSRF protection
  - Rate limiting
  - Input validation improvements

- [ ] **Compliance**
  - Audit logging
  - Compliance reports
  - Security scanning integration

## 📱 Advanced Features

- [ ] **Multi-Server Management**
  - Manage multiple servers from one interface
  - Server groups
  - Cluster management
  
## 🤝 How to Contribute

### For VM Testing:
1. Set up a test environment with QEMU/KVM
2. Test VM creation with different parameters
3. Document any bugs or issues
4. Suggest improvements to the VM management UI

### For New Features:
1. Check this TODO list for areas needing work
2. Open an issue to discuss your approach
3. Submit a PR with your implementation
4. Update documentation

### For Bug Fixes:
1. Check existing issues
2. Reproduce the bug
3. Create a fix with tests
4. Submit a PR

## 📝 Notes

- Items marked with ⚠️ are critical for production use
- Items marked with 🎯 are good first issues for new contributors
- See CONTRIBUTING.md for detailed guidelines

---

**Last Updated:** February 6, 2026

**Priority Legend:**
- 🚨 High Priority - Critical functionality
- 🔧 Medium Priority - Important improvements
- 📦 Low Priority - Nice to have
