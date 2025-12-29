# Jellyfin Media Server

The Free Software Media System - Your media, your way.

## Features

- 🎬 Movies and TV shows
- 🎵 Music streaming
- 📚 Books and comics
- 📷 Photo libraries
- 📺 Live TV and DVR
- 🎨 Beautiful web interface
- 📱 Mobile apps (iOS, Android)
- 🆓 Completely free and open source

## Configuration

### Default Ports
- **8096**: Web interface (HTTP)
- **8920**: Web interface (HTTPS)

### Volumes
- `/config`: Jellyfin configuration and database
- `/cache`: Transcoding cache
- `/media`: Your media library

## First Time Setup

1. Access Jellyfin at `http://your-server-ip:8096`
2. Follow the setup wizard
3. Create an admin account
4. Add your media libraries (point to `/media`)
5. Configure metadata providers

## Media Organization

Organize your media in folders:
```
/mnt/media/
├── movies/
├── tv-shows/
├── music/
└── photos/
```

## Hardware Acceleration

For hardware transcoding, you may need to:
1. Pass through GPU devices
2. Install appropriate drivers on host
3. Enable hardware acceleration in Jellyfin settings

## Advantages over Plex

- ✅ Completely free (no Plex Pass needed)
- ✅ No external authentication required
- ✅ No telemetry or tracking
- ✅ Open source

## Official Documentation

https://jellyfin.org/docs/
