# Nextcloud

A safe home for all your data. Access & share your files, calendars, contacts, mail & more from any device.

## Features

- 📁 File sync and share
- 📅 Calendar and contacts
- 📧 Mail client
- 💬 Chat and video calls
- 📝 Collaborative document editing
- 🔐 End-to-end encryption
- 📱 Mobile apps for iOS and Android

## Configuration

### Default Access
- Web interface: `http://your-server-ip:8080`

### Default Credentials
On first launch, you'll create an admin account.

### Database
- MariaDB 10.11
- Database name: `nextcloud`
- User: `nextcloud`
- Password: `nextcloud` (change in production!)

### Volumes
- `/var/www/html`: Nextcloud application and user data
- Database: Stored in `/opt/upservx/data/nextcloud-db`

## First Time Setup

1. Access Nextcloud at `http://your-server-ip:8080`
2. Create an admin account
3. The database settings are pre-configured (MySQL/MariaDB)
4. Click "Finish setup"

## Security Recommendations

1. **Change database passwords** in the docker-compose.yml file before first start
2. Set up **HTTPS** with a reverse proxy (nginx, traefik)
3. Configure **trusted domains** in Nextcloud settings
4. Enable **two-factor authentication**

## Performance Tips

- Consider using Redis for caching
- Set up a separate database server for better performance
- Use external storage for large files

## Official Documentation

https://docs.nextcloud.com/
