Immich is a self-hosted, high-performance photo and video backup solution. It provides a Google Photos-like experience with automatic mobile backup, AI-powered search, facial recognition, object detection, and shared albums – running entirely on your own server.

## Features

- 📱 Automatic backup from iOS and Android via the Immich app
- 🔍 AI-powered search (objects, scenes, faces)
- 👤 Facial recognition and person tagging
- 🗺️ Map view based on photo GPS metadata
- 📁 Albums, shared albums, and archive
- 📊 Storage usage statistics per user
- 🎞️ Video support with transcoding
- 👥 Multi-user with admin and regular accounts
- 🔌 REST API and CLI for external integrations
- 📦 Import from Google Takeout

## Default Access

- **URL:** `http://<your-server>:2283`
- On first visit, you are prompted to create the admin account.

## Mobile Apps

Download the **Immich** app and point it to `http://<your-server>:2283`.

- [iOS – App Store](https://apps.apple.com/app/immich/id1613945652)
- [Android – Google Play](https://play.google.com/store/apps/details?id=app.alextran.immich)

## Stack Components

| Container | Description |
|---|---|
| `immich-server` | Main API server and web UI |
| `immich-machine-learning` | AI/ML service (face detection, CLIP search) |
| `immich-redis` | Job queue and caching |
| `immich-db` | PostgreSQL with pgvecto-rs (vector search extension) |

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upcode-harbor/data/immich/upload` | All uploaded photos and videos |
| `/opt/upcode-harbor/data/immich/model-cache` | Downloaded AI model files |
| `/opt/upcode-harbor/data/immich-db` | PostgreSQL database |

## External Library (optional)

To index an existing photo collection without re-uploading, add an external library path:

```yaml
volumes:
  - /path/to/your/photos:/usr/src/app/external:ro
```

Then configure the external library in the admin UI under **Administration → Libraries**.

## Updating

Immich releases frequently. To update:

```bash
docker compose pull
docker compose up -d
```

> ⚠️ Always check the [release notes](https://github.com/immich-app/immich/releases) before updating – breaking changes are occasionally introduced.

## Official Documentation

https://immich.app/docs/
