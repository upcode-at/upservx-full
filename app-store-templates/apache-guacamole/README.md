# Apache Guacamole

Apache Guacamole is a clientless remote desktop gateway. It supports standard protocols such as VNC, RDP, and SSH. No plugins or client software are required – access your desktops from any HTML5-capable browser.

## Components

| Container | Role |
|---|---|
| `guacamole-guacd` | Guacamole daemon – handles protocol-level connections (VNC, RDP, SSH) |
| `guacamole-web` | Web application – serves the browser-based UI |
| `guacamole-postgres` | PostgreSQL database – stores users, connections, and settings |

## Ports

| Port | Purpose |
|---|---|
| 8080 | Guacamole web interface |

## First-Time Setup: Database Initialization

Before starting the containers for the first time, the database schema must be imported.

**Step 1 – Create the init directory:**
```bash
mkdir -p /opt/upservx/data/apache-guacamole/init
```

**Step 2 – Generate the SQL init script:**
```bash
docker run --rm guacamole/guacamole:latest /opt/guacamole/bin/initdb.sh --postgresql \
  > /opt/upservx/data/apache-guacamole/init/initdb.sql
```

**Step 3 – Install the app via the Upcode Harbor App Store**, then start the containers. PostgreSQL will automatically execute `initdb.sql` on first run.

## Accessing Guacamole

Open your browser and navigate to:

```
http://<your-server-ip>:8080/guacamole
```

**Default credentials:**
- Username: `guacadmin`
- Password: `guacadmin`

> Change the default password immediately after first login!

## Adding Connections

1. Log in as `guacadmin`
2. Go to **Settings → Connections → New Connection**
3. Choose a protocol (RDP, VNC, SSH) and enter the target host details
4. Save and click the connection to start a session

## More Information

- [Apache Guacamole Website](https://guacamole.apache.org)
- [GitHub](https://github.com/apache/guacamole-server)
- [Documentation](https://guacamole.apache.org/doc/gug/)
