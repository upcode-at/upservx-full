# upservx-cli

Command-line interface for [UpservX](https://github.com/upcode-at/upservx).  
After installation the `upservx` command is available system-wide.

## Requirements

- Python 3.8+
- UpservX service running (default: `http://127.0.0.1:9500`)

Dependencies are managed via a dedicated virtualenv that `install.sh` creates automatically at `upservx-cli/venv/`.

| Package | Version | Purpose |
|---------|---------|---------|
| `requests` | 2.32.x | HTTP client for the UpservX API |
| `rich` | 13.9.x | Colored terminal output and tables |

## Usage

```bash
upservx <command> <action> [options]
```

### Service Management

```bash
upservx service status       # Show systemd service status
upservx service start        # Start the UpservX service
upservx service stop         # Stop the UpservX service
upservx service restart      # Restart the UpservX service
```

### Container Management

```bash
upservx containers list                      # List all containers
upservx containers start  <name>             # Start a container
upservx containers stop   <name>             # Stop a container
upservx containers restart <name>            # Restart a container
upservx containers remove  <name>            # Remove a container
upservx containers logs    <name> [-n N]     # Show container logs
upservx containers inspect <name>            # Inspect a container
```

### System

```bash
upservx system info          # Show system information
upservx system stats         # Show CPU, memory and disk usage
upservx system services      # List systemd services
```

### Logs

```bash
upservx logs show [-n N]     # Show last N lines from the log file
upservx logs follow          # Follow the log in real-time
```

### App Store

```bash
upservx apps list                 # List available apps
upservx apps info <app>           # Show app details
upservx apps install <app>        # Install an app
```

### Backups

```bash
upservx backup list               # List all backups
upservx backup create [--target]  # Create a backup
upservx backup status             # Show backup job status
```

## Configuration

The CLI reads configuration from `/etc/upservx-cli.conf` (JSON) or environment variables:

| Variable            | Default                   | Description            |
|---------------------|---------------------------|------------------------|
| `UPSERVX_API_URL`   | `http://127.0.0.1:9500`   | Backend API base URL   |
| `UPSERVX_TOKEN`     | *(empty)*                 | Bearer auth token      |

Example `/etc/upservx-cli.conf`:

```json
{
  "api_url": "http://127.0.0.1:9500",
  "token": "your-token-here"
}
```

## Structure

```
upservx-cli/
├── upservx              ← executable (installed to /usr/local/bin/upservx)
├── cli/
│   ├── main.py          ← argument parser and entry point
│   ├── config.py        ← configuration loading
│   ├── api.py           ← HTTP client (stdlib only)
│   ├── output.py        ← colored output helpers
│   └── commands/
│       ├── service.py   ← service start/stop/restart/status
│       ├── containers.py
│       ├── system.py
│       ├── logs.py
│       ├── apps.py
│       └── backup.py
└── README.md
```
