## Release v0.3.0 - RBAC, VM Portability & App Store Expansion 🔐

**Release Date:** 2026-03-13

### 🎉 What's New in UpservX v0.3.0

This release is the biggest security and feature update since the initial launch. The authentication layer has been fully rewritten around HttpOnly session cookies and Linux-group-based access control, VMs can now be exported and imported as industry-standard OVA/OVF packages, the App Store grows by 19 new one-click templates, and the UI receives a full customization system together with a polished light/dark/system theme toggle.

### ✨ Highlights

#### 🔐 Group-based Access Control (RBAC)
- Linux-group mapping: `docker`, `libvirt`, `tty`, `disk`, `adm`, `sudo` and more
- Per-path HTTP 403 enforcement in the API middleware
- Permission-aware sidebar — items hidden when the user lacks the required group
- New `GET /auth/me` and `GET /info` endpoints

#### 🍪 HttpOnly Session Cookies
- Auth token moved from `localStorage` to `HttpOnly SameSite=Lax` cookie
- `admin:admin` Basic-auth fallback permanently removed
- Session verified on page load via `/auth/me` — no sidebar flash

#### 📦 VM OVA/OVF Export & Import
- Export running or stopped VMs as standards-compliant OVA or OVF packages
- Import `.ova` / `.ovf` files from any compatible hypervisor
- SHA-256 manifest and VMDK conversion via `qemu-img` included

#### 🛒 19 New App Store Templates
Traefik, Harbor, GitLab, Keycloak, OpenLDAP, Docker Registry, Kafka, Elasticsearch, Mailcow, Loki, MotionEye, RustDesk, Guacamole, ONLYOFFICE, Roundcube, Neo4j, RabbitMQ, OctoPrint, Tunarr

#### 🎨 Application Customization & Theme Toggle
- Custom logo, login banner text and background image via Settings
- Light/Dark toggle + System mode button in the sidebar

### 📄 Full Release Notes
See [releases/0.3.0.md](releases/0.3.0.md) for complete details including all API changes and upgrade notes.