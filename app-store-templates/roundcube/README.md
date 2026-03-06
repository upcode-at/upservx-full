# Roundcube

Roundcube is an open-source, browser-based IMAP email client. It provides a desktop-like user experience directly in the browser with a rich plugin ecosystem.

## Ports

| Port | Purpose |
|---|---|
| 8090 | Roundcube web interface |

## Required Configuration

Before starting, edit `docker-compose.yml` and set your mail server addresses:

| Variable | Default | Description |
|---|---|---|
| `ROUNDCUBEMAIL_DEFAULT_HOST` | `ssl://mail.example.com` | IMAP server (prefix `ssl://` for IMAPS, `tls://` for STARTTLS) |
| `ROUNDCUBEMAIL_DEFAULT_PORT` | `993` | IMAP port |
| `ROUNDCUBEMAIL_SMTP_SERVER` | `tls://mail.example.com` | SMTP server |
| `ROUNDCUBEMAIL_SMTP_PORT` | `587` | SMTP port |

Common setups:

| Protocol | Host prefix | Port |
|---|---|---|
| IMAPS | `ssl://` | 993 |
| IMAP + STARTTLS | `tls://` | 143 |
| SMTPS | `ssl://` | 465 |
| SMTP + STARTTLS | `tls://` | 587 |

## Database

By default **SQLite** is used – suitable for small setups. For larger deployments, switch to MySQL/PostgreSQL by adding a database service and setting:

```yaml
- ROUNDCUBEMAIL_DB_TYPE=mysql
- ROUNDCUBEMAIL_DB_HOST=db
- ROUNDCUBEMAIL_DB_NAME=roundcube
- ROUNDCUBEMAIL_DB_USER=roundcube
- ROUNDCUBEMAIL_DB_PASSWORD=changeme
```

## Accessing Roundcube

Open your browser and navigate to:

```
http://<your-server-ip>:8090
```

Log in with your full email address and IMAP password.

## Included Plugins

| Plugin | Purpose |
|---|---|
| `archive` | Move messages to an Archive folder |
| `zipdownload` | Download multiple attachments as ZIP |
| `managesieve` | Manage server-side mail filters (Sieve) |

Add more plugins by editing the `ROUNDCUBEMAIL_PLUGINS` environment variable (comma-separated list).

## Integration with Mailcow

If you are running the **Mailcow** app from this store, configure Roundcube as follows:

```yaml
- ROUNDCUBEMAIL_DEFAULT_HOST=ssl://mail.example.com
- ROUNDCUBEMAIL_DEFAULT_PORT=993
- ROUNDCUBEMAIL_SMTP_SERVER=tls://mail.example.com
- ROUNDCUBEMAIL_SMTP_PORT=587
```

Replace `mail.example.com` with your `MAILCOW_HOSTNAME`.

## More Information

- [Roundcube Website](https://roundcube.net)
- [GitHub](https://github.com/roundcube/roundcubemail)
- [Docker Hub](https://hub.docker.com/r/roundcube/roundcubemail)
- [Plugin Repository](https://plugins.roundcube.net)
