# Mailcow – Dockerized Mail Server

Mailcow is a complete, self-hosted mail server suite based on Docker. It bundles everything needed for a production-grade mail setup in a single stack.

## Included Services

| Container | Purpose |
|---|---|
| `postfix-mailcow` | MTA – sends and receives email |
| `dovecot-mailcow` | IMAP/POP3 – email retrieval |
| `rspamd-mailcow` | Spam filter and DKIM signing |
| `clamd-mailcow` | ClamAV antivirus |
| `sogo-mailcow` | Webmail + CalDAV/CardDAV groupware |
| `nginx-mailcow` | Reverse proxy + Admin UI |
| `php-fpm-mailcow` | Admin web interface backend |
| `mysql-mailcow` | MariaDB database |
| `redis-mailcow` | Cache and session store |
| `unbound-mailcow` | Local DNS resolver |
| `acme-mailcow` | Let's Encrypt SSL automation |
| `netfilter-mailcow` | Fail2ban-style IP blocking |
| `watchdog-mailcow` | Health monitoring |
| `dockerapi-mailcow` | Container management API |
| `olefy-mailcow` | OLE/Office file analysis |
| `ofelia-mailcow` | Cron job scheduler |
| `memcached-mailcow` | Object cache for SOGo |

## Ports

| Port | Protocol | Purpose |
|---|---|---|
| 25 | TCP | SMTP (inbound/relay) |
| 80 | TCP | HTTP (ACME challenge, redirect) |
| 110 | TCP | POP3 |
| 143 | TCP | IMAP |
| 443 | TCP | HTTPS (Admin UI + Webmail) |
| 465 | TCP | SMTPS (implicit TLS) |
| 587 | TCP | Submission (STARTTLS) |
| 993 | TCP | IMAPS |
| 995 | TCP | POP3S |
| 4190 | TCP | Sieve (mail filtering) |

## Before You Start – Required Changes

Edit `docker-compose.yml` and replace all placeholder values:

| Variable | Where | Description |
|---|---|---|
| `mail.example.com` | `MAILCOW_HOSTNAME` + `x-env-common` | Your mail server FQDN |
| `changeme_db_password` | `DBPASS` + `mysql` service | MariaDB user password |
| `changeme_db_root_password` | `DBROOT` + `MYSQL_ROOT_PASSWORD` | MariaDB root password |
| `changeme_redis_password` | `REDISPASS` + redis `command` | Redis password |
| `Europe/Berlin` | `TZ` | Your timezone |

> Both the `x-env-common` block AND the individual service definitions must use the same password values.

Generate strong passwords with:
```bash
openssl rand -hex 32
```

## DNS Records

These DNS records are **required** for a functional mail server:

| Type | Name | Value |
|---|---|---|
| A | mail.example.com | `<your-server-ip>` |
| MX | example.com | mail.example.com (priority 10) |
| TXT | example.com | `v=spf1 mx ~all` |
| TXT | \_dmarc.example.com | `v=DMARC1; p=none; rua=mailto:postmaster@example.com` |
| CNAME | autodiscover.example.com | mail.example.com |
| CNAME | autoconfig.example.com | mail.example.com |

DKIM keys are generated automatically – the record to add will be shown in the Admin UI after first start.

## System Requirements

| Resource | Minimum |
|---|---|
| RAM | 4 GB (6 GB+ recommended) |
| CPU | 2 cores |
| Disk | 20 GB+ |
| OS | 64-bit Linux with Docker |

## Accessing the Admin UI

After startup (first boot takes several minutes due to ClamAV DB download):

```
https://mail.example.com
```

Default credentials:
- Username: `admin`
- Password: `moohoo`

> **Change the admin password immediately after first login!**

## Let's Encrypt SSL

SSL certificates are requested automatically if:
- `SKIP_LETS_ENCRYPT` is set to `n`
- Port 80 is publicly reachable
- DNS A record for `MAILCOW_HOSTNAME` points to your server

For local/internal setups, set `SKIP_LETS_ENCRYPT=y` – a self-signed certificate will be used instead.

## Accessing Webmail (SOGo)

```
https://mail.example.com/SOGo
```

## Backup

Important data persisted in Docker named volumes:
- `vmail-vol-1` – All mailboxes
- `mysql-vol-1` – Database (domains, mailboxes, aliases, settings)
- `crypt-vol-1` – Mail encryption keys
- `rspamd-vol-1` – Rspamd data

Config files and SSL certs are stored under `/opt/upcode-harbor/data/mailcow/`.

## More Information

- [Mailcow Website](https://mailcow.email)
- [GitHub](https://github.com/mailcow/mailcow-dockerized)
- [Documentation](https://docs.mailcow.email)
- [Community Forum](https://community.mailcow.email)
