# App Store Templates

**Directory:** `app-store-templates/`

---

## Overview

The `app-store-templates/` directory contains Docker Compose templates for all 49 available applications. Each app has its own subdirectory with:

- `app.json` – App descriptor
- `docker-compose.yml` – Docker Compose configuration
- `README.md` – App-specific documentation (optional)
- `icon.png` or `icon.svg` – App icon (optional)

---

## Directory Structure

```
app-store-templates/
├── adminer/
├── apache-guacamole/
├── apache-kafka/
├── docker-registry/
├── domain-locker/
├── elasticsearch/
├── emby/
├── gitea/
├── gitlab/
├── grafana/
├── harbor/
├── home-assistant/
├── influxdb/
├── jellyfin/
├── jenkins/
├── jitsi/
├── jupyter/
├── keycloak/
├── loki/
├── mailcow/
├── mongodb/
├── motioneye/
├── mysql/
├── n8n/
├── neo4j/
├── nextcloud/
├── nginx-proxy-manager/
├── octoprint/
├── ombi/
├── onlyoffice-docs/
├── openldap/
├── paperless-ngx/
├── phpmyadmin/
├── pihole/
├── plex/
├── postgres/
├── prometheus/
├── rabbitmq/
├── redis/
├── roundcube/
├── rustdesk/
├── teamspeak/
├── traefik/
├── tunarr/
├── typo3/
├── uptime-kuma/
├── vaultwarden/
└── wordpress/
```

---

## app.json Reference

Full schema of an app descriptor:

```json
{
  "id": "app-id",
  "name": "Display Name",
  "description": "Short description of the application",
  "category": "Category",
  "tags": ["tag1", "tag2"],
  "icon": "icon.png",
  "version": "1.0",
  "author": "Author",
  "website": "https://example.com",
  "documentation": "https://docs.example.com",
  "license": "MIT",
  "ports": [
    {
      "host": 8080,
      "container": 80,
      "protocol": "tcp",
      "description": "Web UI"
    }
  ],
  "volumes": [
    {
      "host": "/opt/upservx/app-store/app-id/data",
      "container": "/data",
      "description": "App data"
    }
  ],
  "env": [
    {
      "name": "ENV_VAR_NAME",
      "label": "Display Label",
      "description": "What this variable does",
      "default": "default-value",
      "required": true,
      "secret": false,
      "type": "string"
    }
  ],
  "requires": ["other-app-id"],
  "min_ram_mb": 256,
  "min_disk_mb": 1024,
  "networks": ["upservx_default"]
}
```

---

## docker-compose.yml Conventions

All templates follow these conventions:

```yaml
version: "3.8"

services:
  app-name:
    image: image:${VERSION:-latest}
    container_name: ${CONTAINER_NAME:-app-name}
    restart: unless-stopped
    ports:
      - "${HOST_PORT:-8080}:80"
    volumes:
      - "${DATA_DIR:-/opt/upservx/app-store/app-name/data}:/data"
    environment:
      - SOME_VAR=${SOME_VAR:-default}
    networks:
      - upservx_default

networks:
  upservx_default:
    external: true
```

Environment variables use `${VAR:-default}` syntax so templates work both with and without a `.env` file.

---

## Category Overview

| Category | Apps |
|---|---|
| **Database** | Adminer, MySQL, PostgreSQL, MongoDB, Redis, InfluxDB, Neo4j, Elasticsearch, RabbitMQ |
| **Developer Tools** | Gitea, GitLab, Jenkins, Harbor, Docker Registry, JupyterLab |
| **Media** | Jellyfin, Emby, Plex, Ombi, Tunarr |
| **Monitoring** | Grafana, Prometheus, Loki, Uptime Kuma |
| **Home Automation** | Home Assistant, MotionEye, OctoPrint |
| **Communication** | Jitsi, RustDesk, TeamSpeak |
| **Office / Productivity** | Nextcloud, OnlyOffice Docs, Roundcube, Mailcow |
| **Security / Auth** | Vaultwarden, Keycloak, OpenLDAP, Pi-hole |
| **Infrastructure** | Nginx Proxy Manager, Traefik, Apache Kafka |
| **CMS / Web** | WordPress, TYPO3, Domain Locker |
| **Automation** | N8N, Paperless-ngx |
| **Remote Access** | Apache Guacamole |
| **Other** | PHPMyAdmin |

---

## Adding a New App

1. Create a new directory in `app-store-templates/`:
   ```bash
   mkdir app-store-templates/my-app
   ```

2. Create `app.json` – use the schema above

3. Create `docker-compose.yml` – follow the conventions above

4. Optionally add `icon.png` (64×64 or 128×128 px recommended)

5. Optionally add `README.md` with setup instructions

6. Restart the UpservX backend – the app appears in the store automatically

---

## App Installation Path

Installed apps are placed in:
```
/opt/upservx/app-store/<app-id>/
├── docker-compose.yml   (generated with env vars applied)
├── .env                 (generated env file)
└── data/                (volume data, if applicable)
```
