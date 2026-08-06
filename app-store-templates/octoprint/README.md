# OctoPrint

OctoPrint is the leading open-source web interface for 3D printers. It lets you monitor and control your printer from any browser – including live webcam streams, print job management, temperature graphs, and a vast plugin ecosystem.

## Ports

| Port | Purpose |
|---|---|
| 5000 | OctoPrint web interface |
| 8080 | mjpg-streamer webcam stream (if enabled) |

## Connecting Your 3D Printer

To communicate with your printer over USB, the container needs access to the serial device. Edit `docker-compose.yml` and uncomment the relevant lines:

```yaml
devices:
  - /dev/ttyUSB0:/dev/ttyUSB0   # Most USB-to-serial printers (e.g. Ender 3)
  # - /dev/ttyACM0:/dev/ttyACM0 # Some printers (e.g. Prusa MK3)
group_add:
  - dialout
```

Find your printer's device path on the host:
```bash
ls /dev/tty{USB,ACM}*
# or watch for new devices when plugging in:
dmesg | tail -20
```

## Enabling Webcam (mjpg-streamer)

Set the following environment variables in `docker-compose.yml`:

```yaml
- ENABLE_MJPG_STREAMER=true
- CAMERA_DEV=/dev/video0
- MJPG_STREAMER_INPUT=-n -r 1280x720 -f 30
```

Also pass your webcam device to the container:

```yaml
devices:
  - /dev/video0:/dev/video0
```

The webcam stream will be available at:
```
http://<your-server-ip>:8080/?action=stream
```

Configure the stream URL in OctoPrint under **Settings → Webcam & Timelapse**.

## Accessing OctoPrint

Open your browser and navigate to:

```
http://<your-server-ip>:5000
```

On first launch, the setup wizard will guide you through:
1. Access control (create an admin account)
2. Printer profile (bed size, nozzle diameter, etc.)
3. Connectivity check

## Popular Plugins

Install plugins via **Settings → Plugin Manager → Get More**:

| Plugin | Purpose |
|---|---|
| OctoEverywhere | Remote access from anywhere |
| BedLevelVisualizer | Visualize bed mesh leveling |
| PrintTimeGenius | Accurate print time estimation |
| Telegram | Notifications via Telegram |
| Themeify | Custom UI themes |
| TouchUI | Mobile-optimized interface |

## Data Persistence

All OctoPrint data (config, uploads, timelapse videos, logs) is stored in:
```
/opt/upcode-harbor/data/octoprint/
```

## More Information

- [OctoPrint Website](https://octoprint.org)
- [GitHub](https://github.com/OctoPrint/OctoPrint)
- [Docker Hub](https://hub.docker.com/r/octoprint/octoprint)
- [Plugin Repository](https://plugins.octoprint.org)
- [Community Forum](https://community.octoprint.org)
