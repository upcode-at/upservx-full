# API Endpoints Reference

**Backend Base URL:** `http://<host>:9500`

---

## Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/login` | None | Login (returns token) |
| `POST` | `/auth/logout` | Any | Logout |
| `GET` | `/auth/me` | Any | Current user info |
| `GET` | `/auth/permissions` | Any | Permission summary |

---

## System

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | None | API health check |
| `GET` | `/system/info` | Any | Host system information |
| `POST` | `/system/ws-ticket` | Any | Create WebSocket ticket |
| `GET` | `/system/shell` | Shell | System terminal info |
| `WebSocket` | `/system/shell/ws` | Shell (ticket) | Interactive system shell |

---

## Metrics

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/metrics` | Any | Full system snapshot |
| `GET` | `/metrics/cpu` | Any | CPU + history |
| `GET` | `/metrics/memory` | Any | Memory + history |
| `GET` | `/metrics/disk` | Any | Disk usage |
| `GET` | `/metrics/network` | Any | Network stats |
| `GET` | `/metrics/processes` | Any | Process list |
| `GET` | `/metrics/containers` | Containers | Container stats |
| `GET` | `/metrics/temperature` | Any | Temperatures |
| `WebSocket` | `/metrics/ws` | Any (ticket) | Real-time stream |

---

## Containers

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/containers` | Containers | All containers |
| `POST` | `/containers` | Containers | Create container |
| `GET` | `/containers/{name}` | Containers | Container details |
| `DELETE` | `/containers/{name}` | Containers | Delete container |
| `POST` | `/containers/{name}/start` | Containers | Start |
| `POST` | `/containers/{name}/stop` | Containers | Stop |
| `GET` | `/containers/{name}/logs` | Containers | Logs |
| `GET` | `/containers/{name}/stats` | Containers | Stats |
| `POST` | `/containers/{name}/exec` | Containers | Execute command |
| `WebSocket` | `/containers/{name}/terminal` | Containers (ticket) | Interactive terminal |

---

## Images

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/images` | Containers | All images |
| `POST` | `/images/pull` | Containers | Pull image |
| `DELETE` | `/images/{id}` | Containers | Delete image |

---

## App Store

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/app-store/apps` | Containers | App catalog |
| `GET` | `/app-store/apps/{id}` | Containers | App details |
| `GET` | `/app-store/apps/{id}/icon` | None | App icon |
| `POST` | `/app-store/apps/{id}/install` | Containers | Install app |
| `POST` | `/app-store/apps/{id}/uninstall` | Containers | Uninstall |
| `GET` | `/app-store/installed` | Containers | Installed apps |

---

## Virtual Machines

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/vms` | VMs | All VMs |
| `POST` | `/vms` | VMs | Create VM |
| `GET` | `/vms/{name}` | VMs | VM details |
| `DELETE` | `/vms/{name}` | VMs | Delete VM |
| `POST` | `/vms/{name}/start` | VMs | Start |
| `POST` | `/vms/{name}/stop` | VMs | Stop |
| `POST` | `/vms/{name}/force-stop` | VMs | Force stop |
| `POST` | `/vms/{name}/reboot` | VMs | Reboot |
| `POST` | `/vms/{name}/pause` | VMs | Pause |
| `POST` | `/vms/{name}/resume` | VMs | Resume |
| `WebSocket` | `/vms/{name}/vnc/ws` | VMs (ticket) | VNC session |

---

## ISOs

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/isos` | VMs | ISO file list |
| `POST` | `/isos/upload` | VMs | Upload ISO |
| `DELETE` | `/isos/{filename}` | VMs | Delete ISO |
| `GET` | `/isos/{filename}/file` | None | Download ISO |

---

## Storage

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/drives` | Storage | All drives |
| `GET` | `/drives/{name}` | Storage | Drive + SMART |
| `GET` | `/drives/mounts` | Storage | Mount points |
| `POST` | `/drives/{name}/partitions` | Storage | Create partition |
| `DELETE` | `/drives/{name}/partitions/{p}` | Storage | Delete partition |
| `POST` | `/drives/{name}/partitions/{p}/format` | Storage | Format |
| `POST` | `/drives/{name}/partitions/{p}/mount` | Storage | Mount |
| `POST` | `/drives/{name}/partitions/{p}/unmount` | Storage | Unmount |
| `GET` | `/drives/zfs/pools` | Storage | ZFS pools |
| `POST` | `/drives/zfs/pools` | Storage | Create pool |
| `DELETE` | `/drives/zfs/pools/{name}` | Storage | Destroy pool |

---

## Network

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/network/interfaces` | Admin | Interfaces |
| `POST` | `/network/interfaces/{name}/up` | Admin | Enable |
| `POST` | `/network/interfaces/{name}/down` | Admin | Disable |
| `GET` | `/network/docker` | Admin | Docker networks |
| `POST` | `/network/docker` | Admin | Create network |
| `GET` | `/network/dns` | Admin | DNS config |
| `PUT` | `/network/dns` | Admin | Update DNS |

---

## Firewall

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/firewall/rules` | Admin | All rules |
| `POST` | `/firewall/rules` | Admin | Add rule |
| `DELETE` | `/firewall/rules/{id}` | Admin | Delete rule |
| `GET` | `/firewall/status` | Admin | Status |
| `POST` | `/firewall/flush` | Admin | Clear all rules |

---

## Users & Groups

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/users` | Admin | All users |
| `POST` | `/users` | Admin | Create user |
| `PUT` | `/users/{name}` | Admin | Edit user |
| `DELETE` | `/users/{name}` | Admin | Delete user |
| `POST` | `/users/{name}/password` | Admin | Change password |
| `GET` | `/groups` | Admin | All groups |
| `POST` | `/groups` | Admin | Create group |
| `DELETE` | `/groups/{name}` | Admin | Delete group |

---

## Services

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/services` | Admin | All services |
| `POST` | `/services/{name}/start` | Admin | Start |
| `POST` | `/services/{name}/stop` | Admin | Stop |
| `POST` | `/services/{name}/restart` | Admin | Restart |
| `POST` | `/services/{name}/enable` | Admin | Enable autostart |
| `POST` | `/services/{name}/disable` | Admin | Disable autostart |
| `GET` | `/services/{name}/logs` | Admin | Service logs |

---

## Backup

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/backup/jobs` | Admin | All backup jobs |
| `POST` | `/backup/jobs` | Admin | Create job |
| `PUT` | `/backup/jobs/{id}` | Admin | Edit job |
| `DELETE` | `/backup/jobs/{id}` | Admin | Delete job |
| `POST` | `/backup/jobs/{id}/run` | Admin | Run now |
| `GET` | `/backup/results` | Admin | All results |

---

## Reverse Proxy

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/proxy/routes` | Admin | All routes |
| `POST` | `/proxy/routes` | Admin | Create route |
| `PUT` | `/proxy/routes/{id}` | Admin | Edit route |
| `DELETE` | `/proxy/routes/{id}` | Admin | Delete route |
| `POST` | `/proxy/reload` | Admin | Reload proxy |

---

## Notifications

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/notifications/channels` | Admin | All channels |
| `POST` | `/notifications/channels` | Admin | Create channel |
| `DELETE` | `/notifications/channels/{id}` | Admin | Delete channel |
| `POST` | `/notifications/channels/{id}/test` | Admin | Send test |

---

## Logs

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/logs/activity` | Logs | Activity log |
| `GET` | `/logs/system` | Logs | System log |
| `DELETE` | `/logs/activity` | Admin | Clear log |

---

## Settings

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/settings` | Admin | All settings |
| `POST` | `/settings` | Admin | Update settings |
| `GET` | `/settings/customization` | None | Public branding |
| `GET` | `/settings/api-tokens` | Admin | List API token metadata |
| `POST` | `/settings/api-tokens` | Admin | Create scoped API token |
| `DELETE` | `/settings/api-tokens/{token_id}` | Admin | Revoke API token |
| `GET` | `/settings/version` | Any | Version info |

---

## Cluster

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/cluster/init` | Admin | Initialize master |
| `GET` | `/cluster/status` | Admin | Cluster status |
| `GET` | `/cluster/nodes` | Admin | Node list |
| `DELETE` | `/cluster/nodes/{id}` | Admin | Remove node |
| `GET` | `/cluster/token` | Admin | Join token |
| `POST` | `/cluster/register` | Cluster | Register as child |
| `DELETE` | `/cluster/leave` | Cluster | Leave cluster |

---

## Security

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/security/fail2ban` | Admin | All Fail2Ban jails with banned IPs |
| `POST` | `/security/fail2ban/unban` | Admin | Unban an IP from a jail |
| `GET` | `/security/packages` | Admin | Upgradeable package list |
| `POST` | `/security/packages/upgrade` | Admin | Upgrade all packages |
| `POST` | `/security/packages/upgrade/{name}` | Admin | Upgrade a single package |
| `GET` | `/security/certificates` | Admin | SSL/TLS certificate inventory |
| `GET` | `/security/ports` | Admin | Open port list |
| `GET` | `/security/cve` | Admin | CVE scan results (`?limit=300`) |

---

## Auth Header Reference

| Value | Description |
|---|---|
| `Bearer <session-token>` | User API session |
| `Bearer <api-token>` | Role- and scope-bound automation token |
| Signed cluster headers | Internal cluster node access over HTTPS |
| Cookie `auth` | Secure, HttpOnly browser session |

---

## HTTP Status Codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (not authenticated) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 409 | Conflict (resource already exists) |
| 422 | Unprocessable Entity (schema error) |
| 429 | Too Many Requests (rate limited) |
| 500 | Internal Server Error |
