Woodpecker CI is a lightweight, open-source CI/CD engine that runs pipelines in Docker containers. It is a community fork of Drone CI and integrates natively with Gitea, GitHub, GitLab, and Forgejo – making it the ideal CI companion for the Gitea app store template.

## Features

- 🔄 Pipelines defined as `.woodpecker.yml` in each repository
- 🐳 Every step runs in an isolated Docker container
- 🔌 Native integration with Gitea, GitHub, GitLab, Forgejo
- ⚡ Parallel step and matrix build support
- 🔑 Secrets management (per repo, per org, global)
- 📦 Plugin ecosystem (Docker build, SSH deploy, Telegram, Slack, and more)
- 🖥️ Multi-agent support for parallel build capacity
- 🌐 Simple, clean web UI

## Prerequisites

An OAuth2 application must be created in Gitea before starting Woodpecker.

## Gitea OAuth2 Setup

1. In Gitea, go to **User Settings → Applications → OAuth2 Applications**
2. Click **Create OAuth2 Application**
   - Name: `Woodpecker CI`
   - Redirect URI: `http://your-server:8000/authorize`
3. Copy the **Client ID** and **Client Secret**
4. Set them in `docker-compose.yml`:
   ```yaml
   - WOODPECKER_GITEA_CLIENT=<client-id>
   - WOODPECKER_GITEA_SECRET=<client-secret>
   ```

## Configuration

Before starting, update these values in `docker-compose.yml`:

| Variable | Description |
|---|---|
| `WOODPECKER_HOST` | Public URL of your Woodpecker server |
| `WOODPECKER_GITEA_URL` | URL of your Gitea instance |
| `WOODPECKER_GITEA_CLIENT` | OAuth2 Client ID from Gitea |
| `WOODPECKER_GITEA_SECRET` | OAuth2 Client Secret from Gitea |
| `WOODPECKER_AGENT_SECRET` | Random shared secret between server and agent |

Generate a secure agent secret:
```bash
openssl rand -hex 32
```

## Default Access

- **Web UI:** `http://<your-server>:8000`
- Log in with your Gitea account via OAuth2.

## Example Pipeline

Add a `.woodpecker.yml` to your repository:

```yaml
steps:
  test:
    image: node:20-alpine
    commands:
      - npm ci
      - npm test

  build:
    image: node:20-alpine
    commands:
      - npm run build
    when:
      branch: main
```

## Scaling Agents

To increase parallel build capacity, add more agent instances:

```yaml
  woodpecker-agent-2:
    image: woodpeckerci/woodpecker-agent:latest
    container_name: woodpecker-agent-2
    restart: unless-stopped
    environment:
      - WOODPECKER_SERVER=woodpecker-server:9000
      - WOODPECKER_AGENT_SECRET=changeme-random-secret
      - WOODPECKER_MAX_WORKFLOWS=4
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

## Production Database (PostgreSQL)

For production use, switch from SQLite to PostgreSQL:

```yaml
- WOODPECKER_DATABASE_DRIVER=postgres
- WOODPECKER_DATABASE_DATASOURCE=postgres://woodpecker:woodpecker@woodpecker-db/woodpecker?sslmode=disable
```

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upcode-harbor/data/woodpecker-server` | SQLite database and server data |

## Ports

| Port | Description |
|---|---|
| `8000` | Web UI and REST API |
| `9000` | gRPC – agent ↔ server communication |

## Official Documentation

https://woodpecker-ci.org/docs/
