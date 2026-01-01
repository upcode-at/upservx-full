# Uptime Kuma

A fancy self-hosted monitoring tool. Monitor HTTP(s), TCP, DNS, Docker containers and more with beautiful status pages.

## Features

- 📊 **Multiple Monitor Types**: HTTP(s), TCP, Ping, DNS, Docker, Steam Game Server, and more
- 🔔 **Rich Notifications**: 90+ notification services (Discord, Telegram, Slack, Email, etc.)
- 📱 **Status Pages**: Create beautiful public or private status pages
- 🌍 **Multi-Language**: Available in 40+ languages
- 👥 **Multi-User**: Support for multiple users with role-based access
- 📈 **Uptime Statistics**: View uptime percentages and response times
- 🔒 **2FA Support**: Two-factor authentication for enhanced security
- 🎨 **Customizable**: Custom branding for status pages
- 📦 **Docker Monitoring**: Monitor Docker containers directly
- 🔄 **Auto-Update**: Easy update process

## Initial Setup

1. **Start Uptime Kuma**:
   ```bash
   docker-compose up -d
   ```

2. **Access Web Interface**:
   - URL: http://your-server:3001
   - Create your admin account on first visit
   - Set a strong password

3. **First Monitor**:
   - Click "Add New Monitor"
   - Choose monitor type (HTTP, TCP, etc.)
   - Configure check interval
   - Save and start monitoring

## Monitor Types

### HTTP(s) Monitor

Monitor websites and APIs:

- **URL**: Full URL to monitor
- **Method**: GET, POST, PUT, etc.
- **Interval**: Check frequency (20s - 86400s)
- **Accepted Status Codes**: 200-299 by default
- **Keywords**: Check for specific text in response
- **Headers**: Custom HTTP headers
- **Body**: Request body for POST/PUT
- **Certificate Expiry**: Get alerts before SSL expires

### TCP Port Monitor

Monitor TCP ports:

- **Hostname**: Server address
- **Port**: Port number to check
- **Interval**: Check frequency

### Ping Monitor

ICMP ping monitoring:

- **Hostname**: IP address or hostname
- **Interval**: Check frequency
- **Packet Count**: Number of packets

### DNS Monitor

Monitor DNS resolution:

- **Hostname**: Domain to resolve
- **DNS Server**: DNS server to use
- **Record Type**: A, AAAA, CNAME, MX, etc.
- **Expected Value**: Expected IP or value

### Docker Container Monitor

Monitor Docker containers (requires Docker socket):

1. **Mount Docker Socket**:
   ```yaml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock:ro
   ```

2. **Add Monitor**:
   - Type: Docker Container
   - Container Name: Name or ID
   - Interval: Check frequency

### Steam Game Server

Monitor Steam game servers:

- **Server IP**: Game server IP
- **Port**: Game server port
- **Game**: Select game type

## Notifications

Uptime Kuma supports 90+ notification services:

### Popular Services

- **Email**: SMTP configuration
- **Discord**: Webhook URL
- **Telegram**: Bot token + Chat ID
- **Slack**: Webhook URL
- **Microsoft Teams**: Webhook URL
- **PagerDuty**: Integration key
- **Pushover**: User key + API token
- **Webhook**: Custom HTTP webhook
- **Gotify**: Server URL + token
- **Matrix**: Homeserver + access token

### Setup Notification

1. Go to **Settings → Notifications**
2. Click **Setup Notification**
3. Choose notification type
4. Configure service credentials
5. Test notification
6. Save

### Assign to Monitors

- Edit monitor
- Select notification methods
- Choose when to notify (Down, Up, etc.)

## Status Pages

Create public or private status pages:

### Create Status Page

1. **Settings → Status Pages**
2. **Add New Status Page**
3. Configure:
   - **Slug**: URL path (e.g., `status`)
   - **Title**: Page title
   - **Description**: Optional description
   - **Theme**: Light, Dark, or Auto
   - **Public**: Make publicly accessible

### Add Monitors to Page

- Drag monitors from left panel
- Arrange in groups
- Customize group names
- Set visibility

### Custom Branding

- Upload custom logo
- Set custom CSS
- Configure footer text
- Custom domain (via reverse proxy)

### Access Status Page

- Public: `http://your-server:3001/status/slug`
- Private: Requires login

## Multi-User Setup

### Create Users

1. **Settings → Users**
2. **Add User**
3. Set username and password
4. Assign role

### Roles

- **Owner**: Full access
- **Admin**: Manage monitors and settings
- **User**: View and edit assigned monitors
- **Read-Only**: View only access

### Share Monitors

- Edit monitor
- Enable "Share to Other Users"
- Select users or groups

## Advanced Configuration

### Environment Variables

```yaml
environment:
  - TZ=Europe/Berlin                    # Timezone
  - UPTIME_KUMA_DISABLE_FRAME_SENTRY=1  # Disable error tracking
  - NODE_ENV=production                 # Production mode
```

### Custom Port

```yaml
ports:
  - "8080:3001"  # Change host port
```

### Behind Reverse Proxy

**Nginx Configuration**:

```nginx
location / {
    proxy_pass http://localhost:3001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Traefik Labels**:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.uptime-kuma.rule=Host(`status.yourdomain.com`)"
  - "traefik.http.services.uptime-kuma.loadbalancer.server.port=3001"
```

## Monitoring Best Practices

### Check Intervals

- **Critical Services**: 30-60 seconds
- **Important Services**: 2-5 minutes
- **Regular Services**: 5-15 minutes
- **Low Priority**: 30-60 minutes

### Timeout Settings

- Set timeout lower than interval
- Typical: 30-60 seconds for HTTP
- Adjust based on expected response time

### Retry Settings

- Enable retry before marking as down
- Typical: 1-2 retries
- Prevent false positives

### Alert Fatigue

- Use different notification channels for different priority levels
- Group related monitors
- Use maintenance mode during planned downtime

## Maintenance Mode

Schedule maintenance windows:

1. **Edit Monitor**
2. **Maintenance**
3. **Add Maintenance Window**
4. Set:
   - Start time
   - Duration
   - Recurring schedule (optional)

During maintenance:
- Monitoring continues
- No notifications sent
- Status page shows maintenance

## Backup

### Manual Backup

```bash
# Stop container
docker-compose down

# Backup data directory
tar -czf uptime-kuma-backup-$(date +%Y%m%d).tar.gz ./data

# Restart
docker-compose up -d
```

### Restore

```bash
# Stop container
docker-compose down

# Restore backup
tar -xzf uptime-kuma-backup-20240101.tar.gz

# Restart
docker-compose up -d
```

### Automated Backup Script

```bash
#!/bin/bash
BACKUP_DIR="/backups/uptime-kuma"
mkdir -p "$BACKUP_DIR"

cd /path/to/uptime-kuma
docker-compose exec uptime-kuma sh -c "cd /app/data && tar -czf - ." > "$BACKUP_DIR/backup-$(date +%Y%m%d-%H%M%S).tar.gz"

# Keep only last 30 days
find "$BACKUP_DIR" -name "backup-*.tar.gz" -mtime +30 -delete
```

## Database

Uptime Kuma uses SQLite by default:

- **Location**: `./data/kuma.db`
- **Automatic migrations**: On updates
- **No external database needed**

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs -f

# Verify data directory permissions
ls -la ./data

# Fix permissions if needed
sudo chown -R 1000:1000 ./data
```

### Can't Access Web Interface

- Verify port 3001 is not in use: `netstat -tulpn | grep 3001`
- Check firewall rules
- Verify container is running: `docker ps`

### Monitors Showing Incorrect Status

- Check timeout settings
- Verify network connectivity from container
- Test monitor URL from container:
  ```bash
  docker-compose exec uptime-kuma curl -I https://example.com
  ```

### Docker Container Monitoring Not Working

- Verify Docker socket is mounted
- Check socket permissions
- Test Docker access:
  ```bash
  docker-compose exec uptime-kuma docker ps
  ```

### High Memory Usage

- Normal for SQLite database growth
- Consider database cleanup for old data
- Typical usage: 100-300MB

## Updates

### Update to Latest Version

```bash
# Pull new image
docker-compose pull

# Recreate container
docker-compose up -d

# Clean old images
docker image prune -f
```

### Check Version

- Settings → About
- Shows current version and update availability

### Auto-Update (Watchtower)

```yaml
services:
  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 86400 uptime-kuma
```

## API Access

Uptime Kuma has a Socket.IO based API:

- Not RESTful
- Requires Socket.IO client
- Authentication required
- Limited documentation

For programmatic access, consider:
- Using webhooks for alerts
- Exporting status page as JSON
- Direct database access (advanced)

## Integration Examples

### Prometheus/Grafana

Export metrics using custom webhook:

```javascript
// Webhook payload includes:
{
  "monitor": {...},
  "heartbeat": {...},
  "msg": "status message"
}
```

### Home Assistant

Monitor Uptime Kuma status pages:

```yaml
sensor:
  - platform: rest
    resource: http://your-server:3001/api/status-page/your-slug
    name: Service Status
    value_template: "{{ value_json.ok }}"
```

## Security

### Best Practices

- **Strong Passwords**: Use complex admin password
- **2FA**: Enable two-factor authentication
- **HTTPS**: Use reverse proxy with SSL
- **Firewall**: Restrict access if not public
- **Regular Updates**: Keep container updated
- **Backup**: Regular automated backups

### Reverse Proxy (Recommended)

Don't expose Uptime Kuma directly to internet:

1. Use nginx-proxy-manager or similar
2. Enable HTTPS with Let's Encrypt
3. Configure authentication if needed
4. Rate limiting recommended

## Resources

- **Official Website**: https://uptime.kuma.pet/
- **Documentation**: https://github.com/louislam/uptime-kuma/wiki
- **GitHub**: https://github.com/louislam/uptime-kuma
- **Discord**: https://discord.gg/uptime-kuma
- **Reddit**: r/UptimeKuma

## Tips

- Start with few monitors, add gradually
- Test notifications before relying on them
- Use maintenance mode for planned work
- Group related monitors logically
- Keep check intervals reasonable
- Monitor the monitoring (meta-monitoring!)
- Use status pages for transparency
- Regular backups are essential
