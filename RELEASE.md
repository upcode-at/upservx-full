## Release v0.2.0 - Notifications, Activity Logging & Cluster Replication 🔔

**Release Date:** 2026-03-01

### 🎉 What's New in UpservX v0.2.0

This release focuses on observability, alerting and cluster operations. Every important action on your node is now logged to a structured activity log, critical events trigger instant push notifications via Email or Webhook (Discord, Slack, custom), and the cluster now supports full container and VM replication between nodes.

### ✨ Highlights

#### 🔔 Notification System
- Email (SMTP) and Webhook (Discord / Slack / custom) push notifications
- Node hostname included in every message — useful in multi-node setups
- 12 per-event toggles: Container create/start/stop/crash/delete, VM create/start/stop/delete, Backup success/failure, System alert
- Rich context per event (image, ports, CPU, memory, backup size/path, error messages)
- New *Notifications* tab in Settings UI

#### 📋 Structured Activity Logging
- All service modules write to `/var/log/upservx/activity.log`
- Consistent `YYYY-MM-DD HH:MM:SS [TAG] Message` format with INFO / ERROR levels
- 174 cluster `print()` calls now dual-write via `_clog()` helper

#### 🔁 Cluster Replication
- Replicate Docker containers and KVM VMs between nodes from the Cluster UI
- Full export/import including volumes, disk images, port mappings and environment variables
- Manual trigger per replication entry

#### 🗄️ Persistent Storage Mounts
- Drives mounted via UI are persisted to `/etc/fstab` with UUID-based identification
- Automatic fstab cleanup on unmount, backup before every modification

#### 🔒 12 Security Fixes
WebSocket shell auth, debug endpoint removal, path traversal (ISO, tarfile, SSH keys), SSRF, exception leak, rate limiting, input validation, shell allowlist, logout bug.

### 📄 Full Release Notes
See [releases/0.2.0.md](releases/0.2.0.md) for complete details including all API changes and upgrade notes.