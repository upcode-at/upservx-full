# UpservX – Documentation

Welcome to the complete technical documentation for the **UpservX** project.

---

## Table of Contents

### General
- [Architecture](./architecture.md)
- [Installation & Deployment](./installation.md)

### Backend (`upservx-service/`)
| Document | Description |
|---|---|
| [Authentication & Middleware](./backend/authentication.md) | PAM auth, API key, rate limiting, middleware |
| [Permission System](./backend/permissions.md) | Linux groups → subsystem mapping |
| [Container Management](./backend/containers.md) | Docker, LXC, Kubernetes |
| [Virtual Machines](./backend/virtual-machines.md) | QEMU/KVM, libvirt, snapshots |
| [Backup System](./backend/backup.md) | Local & SSH remote, encryption, scheduling |
| [Network Management](./backend/network.md) | Interfaces, gateways, configuration |
| [Storage Management](./backend/storage.md) | Drives, ZFS pools, mount points |
| [Firewall Management](./backend/firewall.md) | nftables, rules, NAT |
| [Reverse Proxy & SSL](./backend/reverse-proxy.md) | Nginx, Certbot, Let's Encrypt |
| [User & Group Management](./backend/users.md) | Linux users, groups, SSH keys |
| [Notifications](./backend/notifications.md) | Email (SMTP), webhooks |
| [Metrics & Monitoring](./backend/metrics.md) | CPU, RAM, disk, network, alerting |
| [App Store](./backend/app-store.md) | Docker Compose templates, installation |
| [Settings](./backend/settings.md) | Hostname, timezone, VPN, API key |
| [Logging](./backend/logging.md) | Activity log, structured logging |
| [Cluster Management](./backend/cluster.md) | Master/child nodes, replication, load balancing |
| [SystemD Services](./backend/services.md) | Service management |
| [Data Models](./backend/models.md) | Pydantic models |

### Frontend (`upservx/`)
- [Frontend Overview & Architecture](./frontend/README.md)
- [Component Reference](./frontend/components.md)

### App Store
- [App Store Templates](./app-store/README.md)

### API
- [API Endpoint Reference](./api/endpoints.md)
