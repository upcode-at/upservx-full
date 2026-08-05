# UpservX - Server Management Platform

<p align="center">
  <img src="upservx/public/logo.png" alt="UpServX Logo" width="400">
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-18.0+-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688.svg)](https://fastapi.tiangolo.com/)

A comprehensive web-based server management platform with Docker container management, integrated app store, backup system, and system monitoring. UpservX simplifies managing your server infrastructure with a modern, user-friendly interface.

## 🚀 Features

- 📦 **Container and VM Management** - Container lifecycle, logs, image management
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

- **Operating System**: Linux Debian
- **Python**: 3.11 or higher
- **Node.js**: 20 or higher
- **Docker/LXD/libvirt/K3s**: Optional installer profiles
- **Root Access**: Required only to run the installer and signed updater

## ⚡ Installation

### Quick Installation

```bash
# Clone repository
git clone --recurse-submodules https://github.com/upcode-at/upservx.git
cd upservx

# Minimal install without the update facility
sudo ./install.sh --disable-updates

# Example production install with containers and signed updates
sudo ./install.sh --profile containers \
  --update-public-key /secure/release-public.pem
```

The installer creates dedicated `upservx` and `upservx-web` accounts, immutable
versioned releases, separate API/frontend/worker systemd units, an HTTPS nginx
entry point, and a post-install privilege/health smoke test. Optional platform
components are installed only when their profile is selected. See
[`docs/installation.md`](docs/installation.md) for checksum requirements and
the signed update workflow.


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
