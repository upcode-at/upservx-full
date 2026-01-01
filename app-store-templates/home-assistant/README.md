# Home Assistant

Open source home automation that puts local control and privacy first. Control all your devices from a single, unified interface.

## Features

- 🏠 **Smart Home Control**: Unified control for thousands of devices
- 🤖 **Automation**: Create powerful automations without coding
- 📱 **Mobile Apps**: iOS and Android companion apps
- 🔌 **2000+ Integrations**: Support for most smart home devices
- 🎨 **Customizable Dashboard**: Create beautiful, personalized dashboards
- 🔒 **Local Control**: Works without cloud dependency
- 🔔 **Notifications**: Get alerts on your devices
- 📊 **Energy Management**: Monitor and optimize energy usage
- 🎙️ **Voice Control**: Alexa, Google Assistant, Siri integration
- 🔐 **Privacy First**: Your data stays on your server

## Initial Setup

1. **Start Home Assistant**:
   ```bash
   docker-compose up -d
   ```

2. **Wait for Initialization**:
   - First start takes 2-5 minutes
   - Check logs: `docker-compose logs -f`

3. **Access Web Interface**:
   - URL: http://your-server:8123
   - Create your admin account
   - Follow the onboarding wizard

4. **Configure Location**:
   - Set your home location for sun/weather
   - Configure timezone (TZ environment variable)

## Device Integration

### USB Devices (Zigbee, Z-Wave)

If you use USB dongles for Zigbee or Z-Wave:

1. **Find Device Path**:
   ```bash
   ls -l /dev/tty*
   ```

2. **Update docker-compose.yml**:
   ```yaml
   devices:
     - /dev/ttyUSB0:/dev/ttyUSB0
   ```

3. **Restart Container**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Popular Integrations

- **Philips Hue**: Automatic discovery on local network
- **MQTT**: Connect IoT devices via MQTT broker
- **Zigbee**: Use Zigbee2MQTT or ZHA integration
- **Z-Wave**: Use Z-Wave JS integration
- **Google Home/Alexa**: Cloud integration for voice control
- **Sonos**: Automatic discovery
- **HomeKit**: Expose devices to Apple HomeKit

## Configuration

### Configuration Files

All configuration is stored in `./config` directory:

- `configuration.yaml`: Main configuration file
- `automations.yaml`: Automation rules
- `scripts.yaml`: Custom scripts
- `scenes.yaml`: Scene definitions
- `secrets.yaml`: Store sensitive data

### Basic configuration.yaml Example

```yaml
# Basic configuration
default_config:

homeassistant:
  name: Home
  latitude: 52.5200
  longitude: 13.4050
  elevation: 34
  unit_system: metric
  time_zone: Europe/Berlin

# Enable the web interface
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.16.0.0/12

# Text to speech
tts:
  - platform: google_translate

# Lovelace dashboard mode
lovelace:
  mode: yaml
```

## Automations

Create automations via:

1. **UI**: Settings → Automations → Create Automation
2. **YAML**: Edit `automations.yaml` directly

### Example Automation

```yaml
- alias: "Turn on lights at sunset"
  trigger:
    - platform: sun
      event: sunset
  action:
    - service: light.turn_on
      target:
        entity_id: light.living_room
```

## Dashboards

### Lovelace UI

Customize your dashboard:

1. Click edit icon (pencil) in top right
2. Add/remove cards
3. Organize views
4. Use YAML mode for advanced customization

### Popular Cards

- **Entities**: Show multiple entities
- **Light**: Control lights with color picker
- **Thermostat**: Climate control
- **Media Control**: Media player control
- **History Graph**: Historical data visualization
- **Weather Forecast**: Weather information

## Mobile App

1. **Download App**:
   - iOS: App Store
   - Android: Google Play

2. **Connect to Server**:
   - Enter your Home Assistant URL
   - Login with your credentials

3. **Features**:
   - Remote access (requires setup)
   - Location tracking
   - Push notifications
   - Shortcuts/widgets

## Add-ons

**Note**: Docker container installation doesn't support add-ons. For add-ons support:

- Use Home Assistant Operating System
- Use Home Assistant Supervised installation

Popular add-ons include:
- Mosquitto MQTT broker
- Node-RED
- File editor
- Samba share
- Let's Encrypt

## Remote Access

### Via Reverse Proxy (Recommended)

Use nginx-proxy-manager or similar:

```yaml
# In nginx proxy manager
Scheme: http
Forward Hostname: homeassistant
Forward Port: 8123
Websockets Support: ON
```

Update `configuration.yaml`:

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.16.0.0/12  # Docker network
```

### Via Nabu Casa Cloud

- Subscription service ($6.50/month)
- Easy remote access
- Alexa/Google Assistant integration
- Supports Home Assistant development

## Backup

### Manual Backup

```bash
# Stop Home Assistant
docker-compose down

# Backup config directory
tar -czf ha-backup-$(date +%Y%m%d).tar.gz ./config

# Restart
docker-compose up -d
```

### Automated Backup

Use a backup script with cron:

```bash
#!/bin/bash
cd /path/to/home-assistant
tar -czf /backups/ha-backup-$(date +%Y%m%d).tar.gz ./config
# Keep only last 7 days
find /backups -name "ha-backup-*.tar.gz" -mtime +7 -delete
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs -f

# Check configuration
docker-compose exec homeassistant hass --script check_config
```

### Can't Access Web Interface

- Verify port 8123 is not blocked by firewall
- Check if container is running: `docker ps`
- Verify network_mode: host is set

### USB Device Not Found

```bash
# List USB devices
ls -l /dev/tty*

# Check device permissions
sudo usermod -a -G dialout $USER

# Verify device mapping in docker-compose.yml
```

### Integrations Not Discovering

- Ensure network_mode: host is set
- Check if devices are on same network
- Some integrations require manual configuration

## Performance Optimization

### Database

By default, Home Assistant uses SQLite. For better performance:

```yaml
recorder:
  db_url: postgresql://user:password@postgres/homeassistant
  purge_keep_days: 7
  exclude:
    domains:
      - automation
      - updater
```

### Resource Usage

- Disable unused integrations
- Reduce recorder history
- Use MariaDB/PostgreSQL for large installations
- Increase container memory if needed

## Advanced Configuration

### MQTT Integration

1. Install MQTT broker (Mosquitto)
2. Add to configuration.yaml:

```yaml
mqtt:
  broker: localhost
  port: 1883
  username: !secret mqtt_user
  password: !secret mqtt_password
```

### Zigbee2MQTT

Run alongside Home Assistant for Zigbee devices:

```yaml
services:
  zigbee2mqtt:
    container_name: zigbee2mqtt
    image: koenkk/zigbee2mqtt
    volumes:
      - ./zigbee2mqtt:/app/data
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
    environment:
      - TZ=Europe/Berlin
```

## Security

- **Change default ports** if exposed to internet
- **Use HTTPS** with valid certificates
- **Enable two-factor authentication**
- **Regular updates**: Check for updates frequently
- **Secure MQTT**: Use authentication and TLS
- **Firewall rules**: Restrict access as needed

## Resources

- **Documentation**: https://www.home-assistant.io/docs/
- **Community Forum**: https://community.home-assistant.io/
- **Discord**: https://discord.gg/home-assistant
- **GitHub**: https://github.com/home-assistant/core
- **Blueprint Exchange**: Pre-made automations

## Tips

- Start with simple automations
- Use the built-in editor for quick changes
- Join the community for help and inspiration
- Regular backups are essential
- Test automations before deploying
- Use templates for advanced automations
- Monitor system health in Configuration → System
