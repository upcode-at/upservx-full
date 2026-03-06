# Tunarr

Tunarr lets you create virtual live TV channels from your existing media libraries in Plex, Jellyfin, or Emby. Channels are exposed as an HDHomeRun device or M3U playlist and can be consumed by any DVR or player that supports IPTV – such as Plex DVR, Emby Live TV, Jellyfin Live TV, or Infuse.

## Ports

| Port | Purpose |
|---|---|
| 8000 | Tunarr web UI and API |

## Accessing Tunarr

Open your browser and navigate to:

```
http://<your-server-ip>:8000
```

## Setup

### 1. Connect Your Media Server

Go to **Settings → Plex / Jellyfin / Emby** and add your media server:

- **Plex**: Enter your Plex server URL and claim token
- **Jellyfin / Emby**: Enter the server URL and an API key

### 2. Create a Channel

Go to **Channels → New Channel** and configure:
- Channel name and number
- Add programming from your libraries (movies, TV show episodes, filler)
- Set a schedule or use shuffle/block shuffle modes

### 3. Connect to Your DVR / Player

Tunarr exposes two endpoints:

| Type | URL |
|---|---|
| M3U Playlist | `http://<your-server-ip>:8000/api/channels.m3u` |
| XMLTV EPG | `http://<your-server-ip>:8000/api/xmltv.xml` |
| HDHomeRun | Auto-discovered on the local network |

**Plex DVR:**
1. Go to Settings → Live TV & DVR → Set Up Plex DVR
2. Tunarr should appear as an HDHomeRun device automatically
3. Add the XMLTV URL as the guide source

**Jellyfin / Emby Live TV:**
1. Go to Dashboard → Live TV → Add Tuner Device → M3U Tuner
2. Enter `http://<your-server-ip>:8000/api/channels.m3u`
3. Add the XMLTV guide: `http://<your-server-ip>:8000/api/xmltv.xml`

## Features

- Schedule movies and TV episodes on custom channels
- Filler/padding content between programs
- Redirect channels (always stream a specific item)
- Time-based programming (e.g. news at 8am, movies at night)
- Compatible with any IPTV-capable player or DVR

## More Information

- [GitHub](https://github.com/chrisbenincasa/tunarr)
- [Documentation](https://tunarr.com/docs)
- [Discord Community](https://discord.gg/tunarr)
