# UpservX CLI

The UpservX CLI (`upservx`) lets you manage your server directly from any terminal — without opening the web interface.

---

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Authentication](#authentication)
- [Command Overview](#command-overview)
- [Command Reference](#command-reference)
  - [auth](#auth)
  - [service](#service)
  - [containers](#containers)
  - [system](#system)
  - [apps](#apps)
  - [backup](#backup)
  - [logs](#logs)
- [Global Options](#global-options)
- [Exit Codes](#exit-codes)

---

## Installation

The CLI is installed automatically by `install.sh` as part of the standard UpservX setup.

```bash
sudo ./install.sh
```

After installation, the `upservx` command is available system-wide:

```bash
upservx --help
upservx --version
```

The CLI lives in the active immutable release under
`/opt/upservx/current/upservx-cli/`. The system-wide wrapper at
`/usr/local/bin/upservx` calls its locked virtual environment automatically.

### Manual / Development Setup

```bash
cd upservx-cli
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 upservx --help
```

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `requests` | 2.33.x | HTTP client for the UpservX API |
| `rich` | 13.9.x | Colored terminal output and tables |

---

## Configuration

The CLI reads configuration from two files. Both are optional JSON files:

| File | Scope | Description |
|------|-------|-------------|
| `/etc/upservx-cli.conf` | system-wide | Written by `install.sh` |
| `~/.upservx-cli.conf` | current user | Written by `upservx auth login` |

The user file takes precedence. Environment variables override everything.

### Config Fields

| Field | Default | Description |
|-------|---------|-------------|
| `api_url` | `http://127.0.0.1:9500` | UpservX backend URL |
| `username` | *(empty)* | Last logged-in username (display only) |
| `token` | *(empty)* | Session or revocable API Bearer token |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `UPSERVX_API_URL` | Override the backend URL |
| `UPSERVX_TOKEN` | Override stored Bearer API token |
| `UPSERVX_USERNAME` | Override the display username |

### Example Config File

```json
{
  "api_url": "https://upservx.example.com/api",
  "token": "your-api-token-here"
}
```

---

## Authentication

The UpservX backend requires authentication on every request. The CLI supports two methods:

| Method | How |
|--------|-----|
| **Session login** | Username/password and, when enabled, an interactive TOTP challenge |
| **Bearer Token** | Set `token` in config or `UPSERVX_TOKEN` env var |

The interactive login flow stores only the issued session token, never the raw
password. The user config is written with mode `0600`.

```bash
# One-time login
upservx auth login

# Verify session
upservx auth whoami

# Remove credentials
upservx auth logout
```

> **Tip:** When connecting to a remote server, set `UPSERVX_API_URL` or update `api_url` in the config file first.

---

## Command Overview

```
upservx <command> <action> [options]
```

| Command | Alias | Description |
|---------|-------|-------------|
| `auth` | — | Login, logout, session management |
| `service` | — | Manage the UpservX systemd service |
| `containers` | `c` | Manage Docker containers |
| `system` | `sys` | System information and monitoring |
| `apps` | — | App Store — browse and install apps |
| `backup` | — | Backup jobs and instances |
| `logs` | — | View the UpservX activity log |

---

## Command Reference

### auth

Manage authentication and sessions.

```
upservx auth <action>
```

| Action | Description |
|--------|-------------|
| `login` | Authenticate with username and password |
| `logout` | Remove stored credentials |
| `whoami` | Show current session info and verify it is still valid |

**Examples**

```bash
# Interactive login (prompts for username and password)
upservx auth login

# A 2FA-enabled account prompts for its TOTP code after password validation.
upservx auth login --username admin

# Check who is logged in and whether the session is still active
upservx auth whoami

# Remove stored credentials
upservx auth logout
```

**Options for `login`**

| Option | Short | Description |
|--------|-------|-------------|
| `--username` | `-u` | Username (prompted if omitted) |
| `--password` | `-p` | Password (prompted securely if omitted) |
| `--totp` | | TOTP code (prompted securely when required) |

---

### service

Manage the UpservX systemd service (`upservx.service`).

```
upservx service <action>
```

| Action | Description |
|--------|-------------|
| `status` | Show current service status (via `systemctl`) |
| `start` | Start the service |
| `stop` | Stop the service |
| `restart` | Restart the service |

**Examples**

```bash
upservx service status
upservx service restart
```

> **Note:** These commands call `systemctl` directly and require root or sudo privileges.

---

### containers

Manage Docker containers through the UpservX API.

```
upservx containers <action> [name] [options]
```

| Action | Arguments | Description |
|--------|-----------|-------------|
| `list` | — | List all containers with name, image, status and ports |
| `start` | `<name>` | Start a stopped container |
| `stop` | `<name>` | Stop a running container |
| `restart` | `<name>` | Restart a container |
| `remove` | `<name>` | Remove a container |
| `logs` | `<name>` | Show container log output |
| `inspect` | `<name>` | Show detailed container information |

**Examples**

```bash
# List all containers
upservx containers list

# Alias shorthand
upservx c list

# Show the last 200 log lines of a container
upservx containers logs myapp --lines 200

# Stop and remove a container
upservx containers stop myapp
upservx containers remove myapp
```

**Options for `logs`**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--lines` | `-n` | `100` | Number of log lines to show |

---

### system

Show system information and resource usage.

```
upservx system <action>
```

| Action | Description |
|--------|-------------|
| `info` | Hardware overview: CPU model, cores, architecture, RAM, disk, GPU, uptime. Includes a service status table (Docker, k3s, LXD, SSH, ZFS). |
| `stats` | Live resource usage: CPU %, RAM, disk, network throughput, uptime, kernel version |
| `services` | List all systemd services with their active state |

**Examples**

```bash
# Full system overview
upservx system info

# Alias shorthand
upservx sys info

# Current resource usage
upservx system stats

# All systemd services
upservx system services
```

---

### apps

Browse and install applications from the integrated App Store.

```
upservx apps <action> [app] 
```

| Action | Arguments | Description |
|--------|-----------|-------------|
| `list` | — | List all available apps with category and description |
| `info` | `<app>` | Show details for a specific app |
| `install` | `<app>` | Deploy an app using its Docker Compose template |

**Examples**

```bash
# Browse all available apps
upservx apps list

# Show details for a specific app
upservx apps info wordpress

# Install an app
upservx apps install grafana
upservx apps install nextcloud
```

> App names correspond to the template IDs in `app-store-templates/`. Common apps: `wordpress`, `nextcloud`, `grafana`, `jellyfin`, `gitea`, `mysql`, `postgres`, `redis`, `pihole`, `vaultwarden`.

---

### backup

Manage backup jobs and view backup instances.

```
upservx backup <action> [options]
```

| Action | Description |
|--------|-------------|
| `list` | List all configured backup jobs |
| `create` | Create a valid scheduled backup job |
| `status` | Show scheduled cron-based backup jobs |

**Examples**

```bash
# List all backup jobs
upservx backup list

# Create a nightly system backup and queue its first run
upservx backup create --name nightly-etc --type system \
  --target /etc --server-id 1 --schedule "0 2 * * *" --run-now

# A container target uses the canonical target prefix
upservx backup create --name app --type container \
  --target container:my-app --server-id 1

# Check scheduled jobs
upservx backup status
```

**Options for `create`**

| Option | Short | Description |
|--------|-------|-------------|
| `--name` | | Backup job name (required) |
| `--type` | | `vm`, `container`, `system`, or `database` (required) |
| `--target` | `-t` | Path, `vm:NAME`, or `container:NAME`; repeatable (required) |
| `--server-id` | | Destination backup-server ID (required) |
| `--schedule` | | Five-field cron expression (default `0 2 * * *`) |
| `--retention-days` | | Archive retention in days (default 30) |
| `--no-compression` | | Write an uncompressed tar archive |
| `--run-now` | | Queue the job immediately after creation |

---

### logs

View the UpservX activity log at `/var/log/upservx/activity.log`.

```
upservx logs <action> [options]
```

| Action | Description |
|--------|-------------|
| `show` | Print the last N lines from the activity log |
| `follow` | Stream the log in real-time (`tail -f`) |

**Examples**

```bash
# Show the last 50 lines (default)
upservx logs show

# Show the last 200 lines
upservx logs show --lines 200
upservx logs show -n 200

# Follow live (Ctrl+C to stop)
upservx logs follow
```

**Options for `show`**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--lines` | `-n` | `50` | Number of lines to display |

---

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--help` | `-h` | Show help for any command or sub-command |
| `--version` | `-v` | Print the CLI version |

```bash
upservx --help
upservx --version
upservx containers --help
upservx containers logs --help
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error (API error, invalid input, etc.) |
| `130` | Interrupted by Ctrl+C |
