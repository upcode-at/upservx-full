MotionEye is a web-based frontend for the motion daemon, turning any camera into a fully featured network camera or video surveillance system. It supports USB cameras, IP cameras (RTSP/MJPEG), and Raspberry Pi camera modules.

## Features

- 📷 Multiple camera support (USB, IP, RTSP, MJPEG)
- 🎥 Live video stream in the browser
- 🔴 Motion detection with configurable sensitivity
- 💾 Video & snapshot recording on motion events
- 📅 Schedule-based recording
- 🔔 Notifications (email, webhooks) on motion
- 🗓️ Timeline view for recorded footage
- 🔐 User authentication
- 🌐 Remote access friendly
- 🖥️ Responsive web interface

## Access

- **Web UI**: `http://localhost:8765`

## Default Credentials

- **Username**: `admin`
- **Password**: *(empty — no password by default)*

> Set a password immediately after first login via **Preferences → Account**.

## Adding Cameras

### USB Camera

Uncomment and adjust the `devices` section in `docker-compose.yml`:

```yaml
devices:
  - /dev/video0:/dev/video0
```

Then in the MotionEye UI: **Add Camera → Local V4L2 Camera** and select the device.

### IP / Network Camera (RTSP)

In the MotionEye UI: **Add Camera → Network Camera**

- **URL**: `rtsp://username:password@192.168.1.100:554/stream`
- **Type**: RTSP or MJPEG depending on your camera

### Raspberry Pi Camera Module

```yaml
devices:
  - /dev/vchiq:/dev/vchiq
  - /dev/video0:/dev/video0
```

## Motion Detection

Configure per camera via ⚙️ → **Motion Detection**:

- **Frame Change Threshold**: sensitivity (lower = more sensitive)
- **Minimum Motion Frames**: avoid false positives
- **Event Gap**: seconds between separate events
- **Pre/Post Capture**: seconds of video before/after motion

## Recording & Storage

Recordings and snapshots are saved to `/var/lib/motioneye` inside the container, which maps to `/opt/upservx/data/motioneye/media` on the host.

Configure storage per camera via ⚙️ → **File Storage**:

- **Recording Mode**: motion-triggered or continuous
- **Movie Format**: H.264, MP4, AVI
- **Preserve Movies**: number of days to keep recordings

## Notifications

Configure via ⚙️ → **Motion Notifications**:

### Email notification

```
Email: your@email.com
SMTP Server: smtp.example.com
SMTP Port: 587
SMTP Username/Password: your credentials
```

### Webhook (e.g. for Home Assistant or n8n)

```
URL: http://your-service/webhook/motion
Method: POST
```

## Behind a Reverse Proxy (Traefik)

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.motioneye.rule=Host(`cam.example.com`)"
  - "traefik.http.routers.motioneye.entrypoints=websecure"
  - "traefik.http.routers.motioneye.tls.certresolver=letsencrypt"
  - "traefik.http.services.motioneye.loadbalancer.server.port=8765"
```

## Official Resources

- GitHub: https://github.com/motioneye-project/motioneye
- Wiki: https://github.com/motioneye-project/motioneye/wiki
- Docker Image: https://github.com/motioneye-project/motioneye/pkgs/container/motioneye

## Notes

- All configuration is persisted in `/opt/upservx/data/motioneye/config/`
- All recordings and snapshots are stored in `/opt/upservx/data/motioneye/media/`
- USB cameras must be passed through via the `devices` key in `docker-compose.yml`
- Set `TZ` to your local timezone to ensure correct timestamps on recordings
- MotionEye pairs well with Home Assistant (motion trigger webhooks) and n8n (automation workflows)
