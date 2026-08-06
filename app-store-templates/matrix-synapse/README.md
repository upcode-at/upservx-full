Matrix Synapse is the reference homeserver implementation for the Matrix open standard – a decentralized, federated, end-to-end encrypted messaging protocol. Element is the official, feature-rich web client for Matrix. Together they provide a self-hosted, privacy-first alternative to Slack, Teams, or Discord with optional federation to the global Matrix network.

## Features

- 🔐 End-to-end encryption (E2EE) by default
- 🌐 Federated – optionally connect to the global Matrix network
- 💬 Rooms, direct messages, voice and video calls
- 📎 File and image sharing
- 🤖 Bot and bridge support (Slack, Discord, Telegram, IRC, WhatsApp, and more)
- 👥 Spaces (channel groups, similar to Discord servers)
- 📱 Mobile apps for iOS and Android (Element)
- 🔌 REST API for integrations and bots

## Stack Components

| Container | Description |
|---|---|
| `synapse` | Matrix homeserver – handles all messaging logic |
| `element` | Web client served at port 8009 |
| `synapse-db` | PostgreSQL database (C locale required) |

## Initial Setup

**1. Generate the Synapse configuration:**
```bash
docker run --rm \
  -e SYNAPSE_SERVER_NAME=your-domain.com \
  -e SYNAPSE_REPORT_STATS=no \
  -v /opt/upcode-harbor/data/synapse:/data \
  matrixdotorg/synapse:latest generate
```

**2. Configure PostgreSQL in `homeserver.yaml`:**

Edit `/opt/upcode-harbor/data/synapse/homeserver.yaml` and replace the default SQLite database section with:

```yaml
database:
  name: psycopg2
  args:
    user: synapse
    password: changeme
    database: synapse
    host: synapse-db
    cp_min: 5
    cp_max: 10
```

**3. Create the Element config:**
```bash
mkdir -p /opt/upcode-harbor/data/element
cat > /opt/upcode-harbor/data/element/config.json << 'EOF'
{
  "default_server_config": {
    "m.homeserver": {
      "base_url": "http://your-domain.com:8008",
      "server_name": "your-domain.com"
    }
  },
  "brand": "Element",
  "integrations_ui_url": "",
  "integrations_rest_url": "",
  "integrations_widgets_urls": [],
  "bug_report_endpoint_url": "",
  "show_labs_settings": false
}
EOF
```

**4. Start the stack:**
```bash
docker compose up -d
```

## Default Access

| Service | URL |
|---|---|
| Element Web UI | `http://<your-server>:8009` |
| Synapse Client API | `http://<your-server>:8008` |
| Synapse Federation | `https://<your-domain>:8448` |

## Creating the First Admin User

```bash
docker exec -it synapse register_new_matrix_user \
  -c /data/homeserver.yaml \
  -u admin -p yourpassword --admin \
  http://localhost:8008
```

## Enabling User Registration (optional)

By default, registration is disabled. To allow new users to register, add to `homeserver.yaml`:

```yaml
enable_registration: true
enable_registration_without_verification: true
```

## Federation (optional)

To federate with the public Matrix network, your server must be reachable at `your-domain.com:8448` with a valid TLS certificate. Add a `.well-known/matrix/server` endpoint at your domain:

```json
{ "m.server": "your-domain.com:8448" }
```

For a private, isolated deployment, set in `homeserver.yaml`:
```yaml
federation_domain_whitelist: []
```

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upcode-harbor/data/synapse` | Synapse config, media store, signing keys |
| `/opt/upcode-harbor/data/synapse-db` | PostgreSQL database |
| `/opt/upcode-harbor/data/element/config.json` | Element web client configuration |

## Ports

| Port | Description |
|---|---|
| `8008` | Client-Server API |
| `8448` | Federation API |
| `8009` | Element Web UI |

## Official Documentation

- Synapse: https://matrix-org.github.io/synapse/latest/
- Element: https://element.io/
- Matrix spec: https://spec.matrix.org/
