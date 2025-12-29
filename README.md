# UpservX - Server Management Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-15.2+-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688.svg)](https://fastapi.tiangolo.com/)

A comprehensive web-based server management platform with Docker container management, integrated app store, backup system, and system monitoring. UpservX simplifies managing your server infrastructure with a modern, user-friendly interface.

## 🚀 Features

- 📦 **Docker Container Management** - Container lifecycle, logs, image management
- 🏪 **Integrated App Store** - 20+ pre-configured apps (WordPress, TYPO3, Nextcloud, Jellyfin, MySQL, PostgreSQL, MongoDB, Redis, Grafana, Prometheus, Pi-hole, and more)
- 💾 **Automated Backup System** - Scheduled backups with Cron, local and SSH remote storage
- 👥 **User & Group Management** - System users, SSH keys, permissions
- 🌐 **Network Management** - Interface configuration, IP management
- 🛠️ **System Services** - SystemD service management and monitoring
- 📊 **System Monitoring** - Real-time metrics (CPU, RAM, Disk, Network)
- 🗄️ **Storage Management** - Disk management, ZFS pools, mount points
- 🎨 **Modern UI** - Dark/Light theme, responsive design with Next.js & Tailwind CSS

## 📦 App Store Templates

UpservX includes over 20 pre-configured app templates for quick deployments:

**CMS & Web:**
- WordPress, TYPO3, Nextcloud, Jitsi

**Media:**
- Jellyfin, Emby, Plex

**Development:**
- Gitea, n8n

**Databases:**
- MySQL, PostgreSQL, MongoDB, InfluxDB, Redis

**Monitoring & Tools:**
- Grafana, Prometheus, phpMyAdmin, Adminer

**Network:**
- Nginx Proxy Manager, Pi-hole, TeamSpeak, Vaultwarden

All templates are located in the `app-store-templates/` folder and can be easily extended.

## 📋 Prerequisites

- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **Python**: 3.8 or higher
- **Node.js**: 18.0 or higher
- **Docker**: Latest version (for container management)
- **Root Access**: Required for system management features

## ⚡ Installation

### Quick Installation

```bash
# Clone repository
git clone https://github.com/upcode-at/upservx.git
cd upservx

# Run installation script
chmod +x install.sh
./install.sh
```

The installation script automatically installs all dependencies and creates the services.


### Access

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000

## 🏗️ Technology Stack

**Frontend:**
- Next.js 15.2+ with React 19
- TypeScript & Tailwind CSS
- shadcn/ui components

**Backend:**
- FastAPI with Python 3.8+
- SQLite with SQLAlchemy ORM
- PAM authentication

**Infrastructure:**
- Docker for container management
- SystemD for service management
- Crontab for backup automation

## 💝 Support

Want to support the project? Here are some ways to help:

### ⭐ GitHub Star
Give the project a star on [GitHub](https://github.com/upcode-at/upservx) - it helps others discover it!

### 🐛 Issues & Feedback
- Report bugs via [GitHub Issues](https://github.com/upcode-at/upservx/issues)
- Share feature requests and suggestions
- Help improve the documentation

### 🤝 Contribute
1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Create a Pull Request

### 💰 Sponsoring
Support development financially:
- [GitHub Sponsors](https://github.com/sponsors/upcode-at)

### 📢 Spread the Word
- Share the project on social media
- Write a blog post about it
- Recommend it to friends and colleagues

Every contribution helps make UpservX better! 🙏

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Contact & Community

- **GitHub**: [upcode-at/upservx](https://github.com/upcode-at/upservx)
- **Issues**: [Bug Reports & Feature Requests](https://github.com/upcode-at/upservx/issues)
- **Discussions**: [GitHub Discussions](https://github.com/upcode-at/upservx/discussions)

---

**UpservX** - Server management made easy 🚀