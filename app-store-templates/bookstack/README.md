BookStack is a simple, self-hosted wiki and documentation platform. Content is organized in a clear three-level hierarchy: **Books → Chapters → Pages** – making it easy to structure and navigate team knowledge bases, runbooks, and internal documentation.

## Features

- 📚 Hierarchical content structure (Books, Chapters, Pages)
- ✏️ WYSIWYG and Markdown editors
- 🔍 Full-text search across all content
- 🖼️ Image and file attachment management
- 👥 Multi-user with role-based permissions
- 🔒 Page-level and book-level visibility controls
- 📤 Export pages as PDF, HTML, or plain text
- 🔗 Cross-page linking and content embedding
- 🎨 Custom logo, app name, and color theming
- 🔌 LDAP/SAML authentication support
- 📊 Audit log for all content changes
- 🌐 Multi-language interface

## Default Access

- **URL:** `http://<your-server>:6875`
- **Default credentials:**
  - Email: `admin@admin.com`
  - Password: `password`

> ⚠️ Change the default admin password immediately after first login.

## Configuration

Before starting, set `APP_URL` in `docker-compose.yml` to the public URL of your BookStack instance (including port). This is required for links, emails, and redirects to work correctly:

```yaml
- APP_URL=http://your-server:6875
```

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upcode-harbor/data/bookstack` | App config, uploads, and attachments |
| `/opt/upcode-harbor/data/bookstack-db` | MariaDB database files |

## Email Configuration (optional)

Add SMTP settings to `docker-compose.yml` for password resets and notifications:

```yaml
- MAIL_DRIVER=smtp
- MAIL_HOST=smtp.example.com
- MAIL_PORT=587
- MAIL_FROM=bookstack@example.com
- MAIL_USERNAME=your-smtp-user
- MAIL_PASSWORD=your-smtp-password
- MAIL_ENCRYPTION=tls
```

## LDAP Authentication (optional)

```yaml
- AUTH_METHOD=ldap
- LDAP_SERVER=ldap://openldap:389
- LDAP_BASE_DN=dc=example,dc=com
- LDAP_FILTER=(&(uid={user}))
- LDAP_USERNAME_ATTRIBUTE=uid
- LDAP_EMAIL_ATTRIBUTE=mail
```

## Backup

To back up BookStack, copy the persistent data directories and dump the database:

```bash
docker exec bookstack-db mysqldump -u bookstack -pchangeme bookstack > bookstack-backup.sql
```

## Official Documentation

https://www.bookstackapp.com/docs/
