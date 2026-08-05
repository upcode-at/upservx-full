# Architecture

## Overview

UpservX is a two-part web application:

```
┌─────────────────────────────┐         ┌─────────────────────────────────┐
│         upservx/            │         │        upservx-service/          │
│  Next.js 16 Frontend        │ ◄─────► │  FastAPI Backend (Python 3.8+)  │
│  React 19 · TypeScript      │  HTTP   │  Uvicorn · SQLAlchemy · Alembic  │
│  Tailwind CSS v4 · Radix UI │  REST   │  PAM Auth · PostgreSQL          │
│  Port 9200                  │  WS     │  API 9500 · Cluster TLS 9501   │
└─────────────────────────────┘         └─────────────────────────────────┘
            │                                          │
            │                                          │
   User Browser                               Linux Host System
                                              Docker Daemon
                                              libvirt/QEMU-KVM
                                              nftables
                                              Nginx
                                              systemd
```

---

## Directory Structure

```
upservx/                        ← Full repository
├── app-store-templates/        ← 49 Docker Compose app templates
├── docs/                       ← This documentation
├── releases/                   ← Release notes
├── upservx/                    ← Next.js frontend
│   ├── app/                    ← Next.js App Router
│   │   ├── layout.tsx          ← Root layout (fonts, theme provider)
│   │   ├── page.tsx            ← Main SPA page
│   │   └── login/             
│   ├── components/             ← 29 React components
│   ├── lib/                    ← Utility functions
│   └── public/                 ← Static assets (logo, images)
└── upservx-service/            ← FastAPI backend
    ├── main.py                 ← FastAPI app, routers, auth middleware (1539 lines)
    ├── permissions.py          ← Group-based access control
    ├── models.py               ← Pydantic data models (440 lines)
    ├── api/                    ← API sub-modules (routers)
    │   ├── cluster.py          ← Cluster management (2312 lines)
    │   ├── containers.py       ← Container API (images, compose)
    │   ├── firewall.py         ← Firewall API
    │   ├── images.py           ← Docker/LXC image API
    │   ├── security.py         ← Security module API
    │   ├── system.py           ← System API
    │   └── customization.py    ← Customisation (logo, colors)
    ├── handlers/               ← Business logic modules (added v0.5.0)
    │   └── security.py         ← Security: Fail2Ban, packages, certs, ports, CVE
    │   ├── system.py           ← System API
    │   └── customization.py    ← Customisation (logo, colors)
    ├── containers.py           ← Docker/LXC/K8s container logic
    ├── vms.py                  ← QEMU/KVM VM management (873 lines)
    ├── backup.py               ← Backup engine (933 lines)
    ├── backup_db.py            ← Backup database (SQLite via SQLAlchemy)
    ├── network.py              ← Network interface management
    ├── storage.py              ← Disk & ZFS management (433 lines)
    ├── firewall.py             ← nftables management (407 lines)
    ├── reverse_proxy.py        ← Nginx + Certbot (473 lines)
    ├── users.py                ← Linux users/groups
    ├── services.py             ← systemd services
    ├── notifications.py        ← Email & webhook
    ├── metrics_collector.py    ← Metrics & alerting (458 lines)
    ├── app_store.py            ← App store logic (194 lines)
      ├── handlers/settings.py    ← Settings, VPN
    ├── upservx_logger.py       ← Activity log (131 lines)
    ├── ssh_keys.py             ← SSH key manager
    ├── crontab_manager.py      ← Cron jobs
    ├── vnc_proxy.py            ← WebSocket VNC proxy
    ├── ws_tickets.py           ← One-time WebSocket tickets
    ├── load_balancer.py        ← Load balancing strategies
    ├── container_sync.py       ← Container sync (cluster)
    ├── compose_manager.py      ← Docker Compose management
    ├── config_manager.py       ← Configuration persistence
    ├── isos.py                 ← ISO image management
    ├── system_utils.py         ← System metrics (psutil)
    └── db/                     ← SQLite database files
```

---

## Request Lifecycle

```
Browser Request
      │
      ▼
CORS Middleware
      │
      ▼
PAM Auth Middleware  ───► 401 (if missing/invalid credentials)
      │
      ▼
Permission Check (permissions.py)  ───► 403 (if group missing)
      │
      ▼
FastAPI Router (main.py, api/*.py)
      │
      ▼
Module Logic (containers.py, vms.py, ...)
      │
      ├── Shell Commands (subprocess → docker, lxc, virsh, nft, ...)
      ├── psutil (CPU, RAM, disk, network)
      └── SQLAlchemy (backup DB, configuration)
```

---

## Authentication Flow

```
Client authenticates
        │
        ├── POST /auth/login → PAM, optional TOTP, revocable signed session
        ├── "Bearer <api-token>" → hash, revocation, expiry, role, and scope checks
        └── Signed cluster headers → peer identity, time window, and replay checks

No Authorization header?
  → Secure HttpOnly cookie named "auth" containing the signed session
```

---

## Technology Stack

| Layer | Technology | Version |
|---|---|---|
| **Frontend** | Next.js | 16.x |
| **Frontend** | React | 19.x |
| **Frontend** | TypeScript | 5.x |
| **Frontend** | Tailwind CSS | 4.x |
| **Frontend** | Radix UI | various |
| **Frontend** | xterm.js | 5.5 |
| **Backend** | Python | 3.8+ |
| **Backend** | FastAPI | 0.128 |
| **Backend** | Uvicorn | 0.32 |
| **Backend** | Pydantic | 2.x |
| **Backend** | SQLAlchemy | 2.0 |
| **Backend** | Alembic | 1.14 |
| **Backend** | Paramiko | 3.5 (SSH) |
| **Backend** | cryptography | 46.x (Fernet) |
| **Backend** | psutil | 6.1 (metrics) |
| **Auth** | python-pam | 2.0 |
| **DB** | PostgreSQL | via psycopg2 |
| **System** | Docker | CLI |
| **System** | LXC/LXD | CLI |
| **System** | QEMU/KVM | via libvirt |
| **System** | nftables | Firewall |
| **System** | Nginx | Reverse proxy |
| **System** | Certbot | SSL |
| **System** | systemd | Services |
