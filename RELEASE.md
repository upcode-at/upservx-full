## Release v0.5.0 - Security Module 🔐

**Release Date:** 2026-05-03

### 🎉 What's New in UpservX v0.5.0

This release introduces the **Security Module** — a dedicated administration area giving server operators a unified view of their system's security posture. Five features are bundled in a single tabbed interface accessible to admin-group users: Fail2Ban management, package upgrade tracking, SSL/TLS certificate inspection, open port scanning and CVE vulnerability scanning via the OSV.dev database.

### ✨ Highlights

#### 🛡️ Fail2Ban Management
- View all configured jails with banned IP counts and total failed attempts
- List all currently banned IPs per jail
- Unban individual IPs directly from the dashboard

#### 📦 Package Upgrade Tracker
- Discover all upgradeable packages (Debian/Ubuntu) at a glance
- Filter to security-only updates
- Upgrade all packages or a single package with one click

#### 🔏 SSL/TLS Certificate Inspector
- Automatic scan of common certificate locations (`/etc/ssl/`, `/etc/letsencrypt/`, `/etc/nginx/`, etc.)
- Status badges: VALID / EXPIRING SOON (< 30 days) / EXPIRED
- Filter by status and sort by days remaining

#### 🌐 Open Port Scanner
- See every listening port on the system (TCP + UDP)
- Filter by protocol and by public vs. loopback address

#### 🐛 CVE Vulnerability Scanner
- Batch-query installed packages against the OSV.dev vulnerability database
- CVSS scores (V2/V3/V4), severity filter and advisory links
- Manual scan trigger — no background polling

### 📄 Full Release Notes
See [releases/0.5.0.md](releases/0.5.0.md) for complete details including all API changes and upgrade notes.