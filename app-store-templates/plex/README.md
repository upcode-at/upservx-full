# Plex Media Server

Stream your media library to any device with Plex Media Server.

## Features

- 📺 Stream movies, TV shows, music, and photos
- 🎨 Beautiful interface on all devices
- 📱 Mobile apps for iOS and Android
- 🖥️ Desktop apps for Windows, Mac, and Linux
- 🌐 Web interface accessible from any browser
- 🔄 Automatic metadata and artwork
- 👥 Multi-user support with parental controls

## Configuration

### Default Ports
- **32400**: Web interface and streaming

### Volumes
- `/config`: Plex configuration and database
- `/transcode`: Temporary transcoding files
- `/media`: Your media library (configure as needed)

## First Time Setup

1. After starting the container, access Plex at `http://your-server-ip:32400/web`
2. Sign in with your Plex account (or create one)
3. Follow the setup wizard to add your media libraries
4. Point to `/media` inside the container for your media files

## Environment Variables

- `PUID=1000`: User ID for file permissions
- `PGID=1000`: Group ID for file permissions
- `TZ=Europe/Vienna`: Timezone for logs and schedules
- `VERSION=docker`: Plex update channel

## Media Storage

By default, media is mapped to `/mnt/media` on your host. You can modify the docker-compose.yml file to point to your actual media location.

## Notes

- Uses `network_mode: host` for best performance and discovery
- Hardware transcoding requires Plex Pass subscription
- First launch may take a few minutes to initialize

## Official Documentation

https://www.plex.tv/
