Mattermost is a secure, open-source messaging platform designed for developer collaboration. It provides team channels, direct messages, file sharing, and extensive integrations – fully self-hosted.

## Features

- 💬 Team channels and direct messages
- 📎 File and image sharing
- 🔍 Full-text message search
- 🔔 Desktop, mobile, and email notifications
- 🔌 Webhooks and integrations (GitHub, GitLab, Jira, and more)
- 🤖 Bot and slash command support
- 📱 Mobile apps for iOS and Android
- 🔐 End-to-end data ownership
- 🌍 Multi-language support
- 📊 Team and user management

## Default Access

- **URL:** `http://<your-server>:8065`
- On first start, you will be guided through the setup wizard to create the first admin account.

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upservx/data/mattermost/config` | Configuration files |
| `/opt/upservx/data/mattermost/data` | User uploads and attachments |
| `/opt/upservx/data/mattermost/logs` | Application logs |
| `/opt/upservx/data/mattermost/plugins` | Installed plugins |
| `/opt/upservx/data/mattermost-db` | PostgreSQL database |

## Configuration

All settings can be managed via the **System Console** (`Main Menu → System Console`) after logging in as admin. Key settings:

- **SMTP**: Required for email notifications and password resets
- **Site URL**: Must be set correctly for links and notifications to work

## Official Documentation

https://docs.mattermost.com/
