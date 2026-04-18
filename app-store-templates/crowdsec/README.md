CrowdSec is a modern, open-source, collaborative intrusion prevention system. It analyzes server logs to detect attacks and malicious behavior, shares threat intelligence with a global community, and blocks bad actors via bouncers (firewall, Nginx, Traefik, and more).

## Features

- 🛡️ Detects SSH brute force, web scans, credential stuffing, and more
- 🌐 Community-sourced blocklist with millions of malicious IPs
- 🔌 Bouncer ecosystem: firewall, Nginx, Traefik, HAProxy, Cloudflare
- 📊 Prometheus metrics and web dashboard
- 🔄 Automatic updates of detection scenarios
- 📦 Collections for Linux, SSH, Nginx, Apache, and many more
- 🔑 Central LAPI for managing multiple bouncers

## Setup

**1. Start CrowdSec (without the bouncer first):**
```bash
docker compose up -d crowdsec
```

**2. Register the firewall bouncer and get its API key:**
```bash
docker exec crowdsec cscli bouncers add firewall-bouncer
```
Copy the generated API key.

**3. Set the key in `docker-compose.yml`:**
```yaml
- CROWDSEC_LAPI_KEY=<your-key-here>
```

**4. Start the firewall bouncer:**
```bash
docker compose up -d crowdsec-firewall-bouncer
```

## Useful Commands

```bash
# View current alerts
docker exec crowdsec cscli alerts list

# View active IP bans (decisions)
docker exec crowdsec cscli decisions list

# Manually ban an IP
docker exec crowdsec cscli decisions add --ip 1.2.3.4

# Remove a ban
docker exec crowdsec cscli decisions delete --ip 1.2.3.4

# Show installed collections and parsers
docker exec crowdsec cscli hub list

# Update all hub items
docker exec crowdsec cscli hub update && docker exec crowdsec cscli hub upgrade
```

## Adding More Log Sources

Mount additional log files into the CrowdSec container and add the corresponding collection:

```bash
# Example: add Apache collection
docker exec crowdsec cscli collections install crowdsecurity/apache2
```

Then add the log mount to `docker-compose.yml`:
```yaml
- /var/log/apache2:/var/log/apache2:ro
```

## CrowdSec Console (optional)

Register your instance with the CrowdSec cloud console for a visual dashboard and additional blocklists:

```bash
docker exec crowdsec cscli console enroll <your-enroll-key>
```

Get your enroll key at https://app.crowdsec.net/

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upservx/data/crowdsec/config` | Parsers, scenarios, acquis config |
| `/opt/upservx/data/crowdsec/data` | SQLite database, blocklists |

## Ports

| Port | Description |
|---|---|
| `8080` | Local API – used by bouncers |
| `6060` | Prometheus metrics endpoint |

## Official Documentation

https://docs.crowdsec.net/
