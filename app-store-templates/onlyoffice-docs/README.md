# ONLYOFFICE Community Edition

The ONLYOFFICE Community Edition stack consists of three services working together:

| Container | Image | Purpose |
|---|---|---|
| `onlyoffice-communityserver` | `onlyoffice/communityserver` | Main portal – CRM, projects, calendar, people |
| `onlyoffice-docs` | `onlyoffice/documentserver` | Online document/spreadsheet/presentation editor |
| `onlyoffice-mailserver` | `onlyoffice/mailserver` | Built-in mail server |
| `onlyoffice-mysql` | `mysql:8.0` | Shared database for all services |

## Ports

| Port | Purpose |
|---|---|
| 8091 | Community Server web interface (main portal) |
| 8090 | Document Server (internal, used by Community Server) |
| 25 | SMTP (incoming mail) |
| 143 | IMAP |
| 587 | SMTP submission (outgoing mail) |
| 993 | IMAPS (encrypted) |
| 5222 | XMPP / Talk |

## Before You Start

**1. Set your mail domain** – edit `docker-compose.yml` and replace `mail.example.com` with your actual domain in the `hostname` field of the mailserver service.

**2. Change the JWT secret** – replace `changeme_use_a_strong_secret` in both the `onlyoffice-docs` and `onlyoffice-communityserver` service definitions. Both values must match exactly:
```bash
openssl rand -hex 32
```

**3. Change MySQL passwords** – replace `onlyoffice_root` and `onlyoffice_password` with secure values consistently across all services.

## Accessing the Portal

After startup (first boot may take several minutes):

```
http://<your-server-ip>:8091
```

Follow the setup wizard to configure the admin account, mail domain, and DNS records.

## DNS Records for Mail

For the mail server to work correctly, set these DNS records for your mail domain:

| Type | Name | Value |
|---|---|---|
| A | mail.example.com | `<your-server-ip>` |
| MX | example.com | mail.example.com |
| TXT | example.com | `v=spf1 mx ~all` |

## More Information

- [ONLYOFFICE Website](https://www.onlyoffice.com)
- [Community Server GitHub](https://github.com/ONLYOFFICE/CommunityServer)
- [Docker Installation Guide](https://helpcenter.onlyoffice.com/installation/community-install-docker.aspx)
