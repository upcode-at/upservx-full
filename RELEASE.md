## Release v0.1.0 - Initial Pre-Release 🚀

### 🎉 What's New in UpservX v0.1.0

**UpservX** is a comprehensive web-based server management platform that simplifies managing your server infrastructure with a modern, user-friendly interface.

### ✨ Key Features

#### 📦 Container & VM Management
- Full container lifecycle management
- Real-time logs and monitoring
- Image management and registry integration
- VM management with VNC support

#### 🏪 Integrated App Store
Over 25 pre-configured application templates for quick deployments:
- **CMS & Web**: WordPress, TYPO3, Nextcloud, Jitsi
- **Media**: Jellyfin, Emby, Plex, Ombi
- **Development**: Gitea, n8n, Jenkins, Jupyter
- **Databases**: MySQL, PostgreSQL, MongoDB, InfluxDB, Redis
- **Monitoring**: Grafana, Prometheus, Uptime Kuma
- **Network**: Nginx Proxy Manager, Pi-hole, TeamSpeak
- **Security**: Vaultwarden, Paperless-ngx

#### 💾 Automated Backup System
- Scheduled backups with Cron
- Local and SSH remote storage
- Encryption and compression
- Recovery functions

#### 👥 User & Group Management
- System user management
- SSH key management
- Permissions and access control

#### 🌐 Network Management
- Network interface configuration
- IP address management
- Firewall rules

#### 🛠️ System Services
- SystemD service management
- Service monitoring and control

#### 📊 System Monitoring
- Real-time metrics (CPU, RAM, Disk, Network)
- Resource monitoring
- Performance analysis

#### 🗄️ Storage Management
- Disk management
- ZFS pool support
- Mount point configuration

#### 🎨 Modern User Interface
- Dark/Light theme support
- Responsive design
- Next.js 16 + Tailwind CSS
- TypeScript for type safety

### 🛠️ Technical Details

**Frontend:**
- Next.js 16.1.6
- React 19.0.0
- TypeScript 5
- Tailwind CSS 4
- Radix UI Components
- xterm.js Terminal Emulation

**Backend:**
- FastAPI 0.128.5
- Python 3.8+
- SQLAlchemy 2.0.36
- PostgreSQL Database
- Pydantic for data validation

**System Requirements:**
- Linux (Debian/Ubuntu recommended)
- Docker (for container management)
- Root access for system functions

### 📦 Installation

```bash
# Clone repository
git clone https://github.com/upcode-at/upservx.git
cd upservx

# Run installation script
chmod +x install.sh
./install.sh
```

**Access:**
- Frontend: http://localhost:9200
- Backend API: http://localhost:9500

### 🔧 Usage

1. **Getting Started**: After installation, access the web interface at http://localhost:9200
2. **App Store**: Install pre-configured applications through the integrated app store
3. **Container Management**: Manage Docker containers through the intuitive interface
4. **Backups**: Configure and monitor automated backup jobs
5. **Monitoring**: Monitor system metrics in real-time

### 📝 Pre-Release Notes

This is a pre-release version (v0.1.0) and may contain unknown issues. It is recommended to:
- Perform regular backups of your data
- Evaluate the software in a test environment first
- Report issues via GitHub issues

### 🤝 Contributing

We welcome feedback and contributions! You can:
- ⭐ Star the project on GitHub
- 🐛 Report bugs and create feature requests
- 🤝 Contribute code via pull requests
- 📢 Share the project in your networks

### 📄 License

This project is licensed under the MIT License.

---

**UpservX v0.1.0** - Server management made easy! 🚀

For detailed documentation, visit the [README.md](https://github.com/upcode-at/upservx/blob/main/README.md).