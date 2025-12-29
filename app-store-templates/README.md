# UpServX App Store Templates

This directory contains pre-configured Docker Compose applications for easy installation through the UpServX App Store.

## Structure

Each app template contains:
- `app.json` - Metadata and configuration
- `docker-compose.yml` - Docker Compose configuration
- `README.md` - Documentation and setup instructions

## Available Apps

### Media
- **Plex** - Media server for streaming movies, TV shows, and music
- **Jellyfin** - Free and open-source media server

### Productivity
- **Nextcloud** - Self-hosted file sync and collaboration platform

### Management
- **Portainer** - Container management platform

## Creating New App Templates

1. Create a new directory: `app-store-templates/your-app/`
2. Add `app.json` with metadata:
```json
{
  "name": "App Name",
  "description": "Short description",
  "version": "latest",
  "category": "media|productivity|management|security|networking|other",
  "icon": "🎬",
  "author": "Author Name",
  "ports": ["8080:80"],
  "volumes": ["/opt/upservx/data/app:/data"],
  "environment": {
    "KEY": "value"
  }
}
```
3. Add `docker-compose.yml` with your compose configuration
4. Add `README.md` with setup instructions

## Installation

The install script will copy these templates to `/opt/upservx/app-store/` on the server.

## Categories

- **media**: Media servers, streaming, entertainment
- **productivity**: File storage, collaboration, office tools
- **management**: Monitoring, container management, administration
- **security**: VPN, firewalls, security tools
- **networking**: DNS, proxies, network tools
- **other**: Everything else
