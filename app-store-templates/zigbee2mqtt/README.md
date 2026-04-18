Zigbee2MQTT bridges Zigbee devices to MQTT, allowing you to control smart home devices from virtually any home automation system – completely locally, without vendor clouds or proprietary bridges. This template includes an Eclipse Mosquitto MQTT broker.

## Features

- 📡 Supports 3000+ Zigbee devices (bulbs, sensors, switches, plugs, locks, and more)
- 🏠 Works with Home Assistant, Node-RED, and any MQTT-compatible system
- ☁️ Fully local – no cloud dependency
- 🌐 Built-in web UI for device pairing and management
- 🔄 OTA firmware updates for supported devices
- 📊 Device state, availability, and attribute reporting via MQTT
- 🗺️ Network map visualization

## Prerequisites

A supported **Zigbee USB adapter** or network adapter must be connected to the host. Common supported adapters:

- SONOFF Zigbee 3.0 USB Dongle Plus (recommended)
- Texas Instruments CC2652P/CC2652R
- ConBee II / RaspBee II (Dresden Elektronik)
- Electrolama zzh!

Check your adapter's device path:
```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

Adjust `/dev/ttyUSB0` in `docker-compose.yml` to match your adapter.

## Initial Configuration

Before the first start, create the Mosquitto config and the Zigbee2MQTT configuration:

**1. Create Mosquitto config:**
```bash
mkdir -p /opt/upservx/data/mosquitto/config
cat > /opt/upservx/data/mosquitto/config/mosquitto.conf << 'EOF'
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
EOF
```

**2. Create Zigbee2MQTT configuration:**
```bash
mkdir -p /opt/upservx/data/zigbee2mqtt
cat > /opt/upservx/data/zigbee2mqtt/configuration.yaml << 'EOF'
homeassistant:
  enabled: false

mqtt:
  server: mqtt://mosquitto:1883

serial:
  port: /dev/ttyUSB0

frontend:
  enabled: true
  port: 8080

advanced:
  log_level: info
EOF
```

**3. Start the stack:**
```bash
docker compose up -d
```

## Default Access

- **Web UI:** `http://<your-server>:8080`
- **MQTT Broker:** `<your-server>:1883`

## Pairing Devices

1. Open the Web UI
2. Click **Permit join (All)** to enable pairing mode
3. Put your Zigbee device into pairing mode (usually hold the button for 5–10 seconds)
4. The device will appear in the UI automatically

## Home Assistant Integration

Add the following to your Home Assistant `configuration.yaml`:

```yaml
mqtt:
  broker: <your-server>
  port: 1883
```

Zigbee2MQTT will automatically publish devices to Home Assistant via MQTT discovery.

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upservx/data/zigbee2mqtt` | Zigbee2MQTT config and device database |
| `/opt/upservx/data/mosquitto/config` | Mosquitto configuration |
| `/opt/upservx/data/mosquitto/data` | Mosquitto persistence data |
| `/opt/upservx/data/mosquitto/log` | Mosquitto logs |

## Official Documentation

https://www.zigbee2mqtt.io/
