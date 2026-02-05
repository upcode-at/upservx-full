# TODO - UpservX Development Roadmap

This file tracks ongoing work, planned features, and areas where contributors can help.

## 🚨 High Priority

### Virtual Machines (VMs)
**Status:** Partially implemented, needs testing and completion

The VM management feature exists but requires thorough testing and completion:

- [ ] **Complete VM Features**
  - [x] VM Cloning functionality ✅ **IMPLEMENTED** - Duplicate button with full disk cloning
  - [ ] VM Snapshots (create, restore, delete)
  - [ ] VM Migration between hosts
  - [ ] VM Templates for quick deployment
  - [ ] Cloud-init integration for automated setup

- [ ] **VM Monitoring**
  - [x] Real-time performance metrics (CPU, RAM) ✅ **IMPLEMENTED** - Live CPU/RAM usage with color coding
  - [ ] Network traffic monitoring per VM
  - [ ] Integration with system overview dashboard
  - [ ] Resource usage history/graphs

- [ ] **VM Networking**
  - Port forwarding rules
  - VLAN support
  - Multiple network interfaces per VM

- [ ] **Storage Management**
  - Disk snapshots
  - Different storage formats (qcow2, raw, vmdk)
  - Storage pool management

- [ ] **VM Import/Export**
  - Export VMs as OVA/OVF
  - Import existing VMs
  - Backup and restore VMs

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

### Monitoring & Alerting

- [ ] **Alert System**
  - Email notifications
  - Telegram/Discord webhooks
  - Slack integration
  - Custom notification channels

- [ ] **Health Checks**
  - Service health monitoring
  - Automatic service restart on failure
  - Custom health check scripts
  - Status page

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

- [ ] **VPN Management**
  - WireGuard support (in addition to OpenVPN)
  - VPN client configuration generator
  - QR codes for mobile clients
  - Connection monitoring

- [ ] **DNS Management**
  - Local DNS server integration
  - DNS record management UI
  - DNSSEC support

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

- [ ] **Documentation**
  - User manual
  - Video tutorials
  - Architecture documentation

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
