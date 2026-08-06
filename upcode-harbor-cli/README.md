# upcode-harbor-cli

Command-line interface for [Upcode Harbor](https://github.com/upcode-at/upcode-harbor).
After installation the `upcode-harbor` command is available system-wide.

## Requirements

- Python 3.8+
- Upcode Harbor service running (default: `http://127.0.0.1:9500`)

Dependencies are managed via a dedicated virtualenv that `install.sh` creates automatically at `upcode-harbor-cli/venv/`.

| Package | Version | Purpose |
|---------|---------|---------|
| `requests` | 2.32.x | HTTP client for the Upcode Harbor API |
| `rich` | 13.9.x | Colored terminal output and tables |

## Usage

```bash
upcode-harbor <command> <action> [options]
```

### Service Management

```bash
upcode-harbor service status       # Show systemd service status
upcode-harbor service start        # Start the Upcode Harbor service
upcode-harbor service stop         # Stop the Upcode Harbor service
upcode-harbor service restart      # Restart the Upcode Harbor service
```

### Container Management

```bash
upcode-harbor containers list                      # List all containers
upcode-harbor containers start  <name>             # Start a container
upcode-harbor containers stop   <name>             # Stop a container
upcode-harbor containers restart <name>            # Restart a container
upcode-harbor containers remove  <name>            # Remove a container
upcode-harbor containers logs    <name> [-n N]     # Show container logs
upcode-harbor containers inspect <name>            # Inspect a container
```

### System

```bash
upcode-harbor system info          # Show system information
upcode-harbor system stats         # Show CPU, memory and disk usage
upcode-harbor system services      # List systemd services
```

### Logs

```bash
upcode-harbor logs show [-n N]     # Show last N lines from the log file
upcode-harbor logs follow          # Follow the log in real-time
```

### App Store

```bash
upcode-harbor apps list                 # List available apps
upcode-harbor apps info <app>           # Show app details
upcode-harbor apps install <app>        # Install an app
```

### Backups

```bash
upcode-harbor backup list               # List all backups
upcode-harbor backup create --name nightly --type system --target /etc --server-id 1
upcode-harbor backup status             # Show backup job status
```

## Structure

```
upcode-harbor-cli/
├── upcode-harbor              ← executable (installed to /usr/local/bin/upcode-harbor)
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
