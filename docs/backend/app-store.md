# App Store

**File:** `upservx-service/app_store.py`
**Templates Directory:** `app-store-templates/`
**Required permission:** `docker` group or admin

---

## Overview

The app store provides a curated collection of Docker Compose templates that can be installed with a single click. Each app consists of:

- An `app.json` descriptor
- A `docker-compose.yml`
- An optional `README.md`
- An optional icon (PNG/SVG)

---

## App Descriptor: `app.json`

```json
{
  "id": "nextcloud",
  "name": "Nextcloud",
  "description": "Self-hosted file sync and collaboration platform",
  "category": "Storage",
  "tags": ["files", "cloud", "sync"],
  "icon": "nextcloud.png",
  "version": "28",
  "author": "Nextcloud GmbH",
  "website": "https://nextcloud.com",
  "documentation": "https://docs.nextcloud.com",
  "ports": [
    {"host": 8080, "container": 80, "description": "Web UI"}
  ],
  "volumes": [
    {"host": "/opt/nextcloud/data", "container": "/var/www/html/data"}
  ],
  "env": [
    {
      "name": "MYSQL_ROOT_PASSWORD",
      "label": "MySQL Root Password",
      "required": true,
      "secret": true
    }
  ],
  "requires": ["mysql"],
  "min_ram_mb": 512,
  "min_disk_mb": 2048
}
```

---

## Available Apps (49 Templates)

| Category | Apps |
|---|---|
| **Database** | Adminer, MySQL, PostgreSQL, MongoDB, Redis, InfluxDB, Neo4j |
| **Dev Tools** | Gitea, GitLab, Jenkins, Harbor (Container Registry), Docker Registry |
| **Media** | Jellyfin, Emby, Plex, Ombi, Tunarr |
| **Monitoring** | Grafana, Prometheus, Loki |
| **Home Automation** | Home Assistant, MotionEye |
| **Communication** | Jitsi, RustDesk, TeamSpeak |
| **Office** | Nextcloud, OnlyOffice Docs, Roundcube, Mailcow |
| **Security** | Vaultwarden, Keycloak, OpenLDAP, Pi-hole |
| **Infrastructure** | Nginx Proxy Manager, Traefik, Elasticsearch, Apache Kafka |
| **CMS / Web** | WordPress, TYPO3 |
| **Other** | N8N, Paperless-ngx, JupyterLab, Domain Locker, PHPMyAdmin, Apache Guacamole, OctoPrint |

---

## Installation Process

```
1. User clicks "Install" in the UI
2. POST /app-store/apps/{id}/install with env vars
3. Backend:
   a. Copies template from app-store-templates/
   b. Creates directory /opt/upservx/app-store/{id}/
   c. Writes docker-compose.yml with substituted env vars
   d. Runs: docker compose -f ... up -d
4. Status is tracked in the installation database
```

---

## Installation Database

App installations are tracked in SQLite (`/etc/upservx/appstore.db`):

```python
class AppInstallation(Base):
    __tablename__ = "installations"
    id: str (PK)       # App ID
    name: str
    status: str        # "running", "stopped", "error"
    installed_at: datetime
    compose_path: str
    env_vars: JSON
    ports: JSON
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/app-store/apps` | All available apps |
| `GET` | `/app-store/apps/{id}` | App details |
| `GET` | `/app-store/apps/{id}/icon` | App icon (public) |
| `POST` | `/app-store/apps/{id}/install` | Install app |
| `POST` | `/app-store/apps/{id}/uninstall` | Uninstall and delete |
| `GET` | `/app-store/installed` | All installed apps |
| `POST` | `/app-store/installed/{id}/start` | Start installed app |
| `POST` | `/app-store/installed/{id}/stop` | Stop installed app |
| `GET` | `/app-store/installed/{id}/status` | Current status |
| `GET` | `/app-store/installed/{id}/logs` | App logs |

---

## Adding Custom Apps

To add a custom app, create a new subdirectory in `app-store-templates/`:

```
app-store-templates/
└── my-app/
    ├── app.json
    ├── docker-compose.yml
    ├── icon.png          (optional)
    └── README.md         (optional)
```

The app will appear in the app store after the backend is restarted (or on next scan).
