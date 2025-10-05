# UpservX - Server Management Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-15.2+-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-009688.svg)](https://fastapi.tiangolo.com/)

A comprehensive web-based server management platform built with Next.js and FastAPI. UpservX provides an intuitive interface for managing virtual machines, containers, backups, system services, users, and network configurations.

## 🚀 Features

### 📦 Container Management
- Docker container lifecycle management (create, start, stop, remove)
- Container monitoring and resource usage
- Real-time container logs viewing
- Container image management and registry operations

### 🖥️ Virtual Machine Management
- VM creation with custom configurations
- VM lifecycle management (start, stop, shutdown, delete)
- ISO image management and VM installation
- VM resource allocation and monitoring

### 💾 Backup System
- **Automated Backup Jobs**: Schedule backups using cron expressions
- **Multiple Backup Types**: Support for VMs, containers, system files, and databases
- **Storage Options**: Local storage and remote SSH servers
- **tar.gz Compression**: Efficient backup archives with compression
- **Backup History**: Track and manage backup instances
- **Crontab Integration**: Automatic scheduling with system cron

### 👥 User & Group Management
- System user and group administration
- SSH key management for secure access
- User permission and group assignment
- Authentication and authorization controls

### 🌐 Network Management
- Network interface configuration
- IP address and subnet management
- Network settings persistence
- Connection monitoring

### 🛠️ System Services
- Systemd service management
- Service status monitoring
- Start, stop, enable, and disable services
- Real-time service logs

### 📊 System Monitoring
- Real-time system metrics (CPU, memory, disk, network)
- Resource usage charts and graphs
- System performance tracking
- Hardware information display

### 🗄️ Storage Management
- Disk drive management and formatting
- ZFS pool creation and management
- Mount point configuration
- Storage usage monitoring

### 🔧 System Settings
- Global system configuration
- Settings persistence and backup
- System-wide preference management
- Configuration import/export

## 🏗️ Architecture

### Frontend (Next.js)
- **Framework**: Next.js 15.2+ with React 19
- **Styling**: Tailwind CSS with shadcn/ui components
- **State Management**: React Hooks and Context API
- **Authentication**: JWT-based authentication
- **UI Components**: Modern, responsive design with dark/light theme support

### Backend (FastAPI)
- **Framework**: FastAPI with Python 3.8+
- **Database**: SQLite with SQLAlchemy ORM
- **Authentication**: PAM integration for system authentication
- **Background Tasks**: Celery for async task processing
- **API Documentation**: Automatic OpenAPI/Swagger documentation

### Key Technologies
- **Frontend**: Next.js, React, TypeScript, Tailwind CSS
- **Backend**: FastAPI, SQLAlchemy, SQLite, Python
- **Infrastructure**: Docker, SSH, Crontab, SystemD
- **Monitoring**: Real-time metrics collection
- **Security**: PAM authentication, SSH key management

## 📋 Prerequisites

- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **Python**: 3.8 or higher
- **Node.js**: 18.0 or higher
- **npm**: 8.0 or higher
- **Docker**: Latest version (for container management)
- **System Access**: Root privileges for system management features

## ⚡ Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/upcode-at/upservx-full.git
cd upservx-full
```

### 2. Run the Installation Script
```bash
chmod +x install.sh
./install.sh
```

The installation script will:
- Install Python dependencies for the backend
- Install Node.js dependencies for the frontend
- Set up the SQLite database
- Configure initial settings
- Create necessary directories

### 3. Start the Services

**Backend (FastAPI):**
```bash
cd upservx-service
sudo python3 main.py
```

**Frontend (Next.js):**
```bash
cd upservx
npm run dev
```

### 4. Access the Application
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 🔧 Manual Installation

### Backend Setup
```bash
cd upservx-service

# Install Python dependencies
pip3 install -r requirements.txt

# Initialize the database
python3 -c "from backup_db import init_db; init_db()"

# Start the FastAPI server
sudo python3 main.py
```

### Frontend Setup
```bash
cd upservx

# Install Node.js dependencies
npm install

# Start the development server
npm run dev

# Or build for production
npm run build
npm start
```

## 📁 Project Structure

```
upservx-full/
├── install.sh                 # Installation script
├── README.md                  # This file
├── upservx/                   # Next.js frontend
│   ├── app/                   # Next.js app directory
│   │   ├── globals.css        # Global styles
│   │   ├── layout.tsx         # Root layout
│   │   ├── page.tsx           # Homepage
│   │   └── login/             # Login page
│   ├── components/            # React components
│   │   ├── ui/                # shadcn/ui components
│   │   ├── auth-provider.tsx  # Authentication provider
│   │   ├── backup-management.tsx # Backup system UI
│   │   ├── containers.tsx     # Container management UI
│   │   ├── dashboard.tsx      # Main dashboard
│   │   ├── virtual-machines.tsx # VM management UI
│   │   └── ...               # Other components
│   ├── lib/                   # Utility libraries
│   │   ├── api.ts            # API client
│   │   └── utils.ts          # Helper functions
│   └── package.json          # Node.js dependencies
└── upservx-service/          # FastAPI backend
    ├── main.py               # FastAPI application
    ├── models.py             # Pydantic models
    ├── backup.py             # Backup system logic
    ├── backup_db.py          # Database operations
    ├── crontab_manager.py    # Cron job management
    ├── containers.py         # Docker operations
    ├── vms.py                # Virtual machine management
    ├── users.py              # User management
    ├── network.py            # Network configuration
    ├── storage.py            # Storage operations
    ├── services.py           # SystemD service management
    ├── system_utils.py       # System utilities
    ├── settings.py           # Settings management
    ├── ssh_keys.py           # SSH key management
    ├── api/                  # API route modules
    │   ├── system.py         # System API endpoints
    │   ├── containers.py     # Container API endpoints
    │   └── images.py         # Image API endpoints
    └── requirements.txt      # Python dependencies
```

## 🔌 API Endpoints

### Authentication
- `POST /auth/login` - User authentication
- `POST /auth/logout` - User logout
- `GET /auth/verify` - Token verification

### System Management
- `GET /system/metrics` - System metrics
- `GET /system/info` - System information
- `POST /system/settings` - Update system settings

### Container Management
- `GET /containers` - List containers
- `POST /containers` - Create container
- `POST /containers/{id}/start` - Start container
- `POST /containers/{id}/stop` - Stop container
- `DELETE /containers/{id}` - Remove container

### Virtual Machines
- `GET /vms` - List virtual machines
- `POST /vms` - Create VM
- `POST /vms/{id}/start` - Start VM
- `POST /vms/{id}/shutdown` - Shutdown VM
- `DELETE /vms/{id}` - Delete VM

### Backup System
- `GET /backup/servers` - List backup servers
- `POST /backup/servers` - Create backup server
- `DELETE /backup/servers/{id}` - Delete backup server
- `GET /backup/jobs` - List backup jobs
- `POST /backup/jobs` - Create backup job
- `POST /backup/jobs/{id}/execute` - Execute backup
- `DELETE /backup/jobs/{id}` - Delete backup job

### User Management
- `GET /users` - List users
- `POST /users` - Create user
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user

For complete API documentation, visit http://localhost:8000/docs when the backend is running.

## 🛡️ Security Features

- **PAM Authentication**: Integration with system PAM for secure login
- **SSH Key Management**: Secure key-based authentication
- **Role-Based Access**: User and group permission management
- **Secure Backup**: Encrypted backup transfers and storage
- **API Security**: JWT tokens and CORS protection

## 📊 Backup System

### Features
- **Multiple Backup Types**: VMs, containers, system files, databases
- **Storage Options**: Local directories or remote SSH servers
- **Automated Scheduling**: Cron-based backup automation
- **Compression**: tar.gz archives for efficient storage
- **Backup History**: Track all backup instances and status

### Backup Types
1. **Virtual Machines**: Full VM disk image backups
2. **Containers**: Container filesystem and configuration
3. **System Files**: Important system directories and files
4. **Databases**: Database dumps and exports

### Storage Configuration
- **Local Storage**: Store backups in local filesystem paths
- **Remote SSH**: Secure backup transfer to remote servers
- **Automatic Cleanup**: Configurable retention policies

## 🔍 Troubleshooting

### Common Issues

**Backend not starting:**
- Ensure Python 3.8+ is installed
- Check if port 8000 is available
- Run with sudo for system management features
- Verify all dependencies are installed

**Frontend not starting:**
- Ensure Node.js 18+ is installed
- Check if port 3000 is available
- Clear npm cache: `npm cache clean --force`
- Reinstall dependencies: `rm -rf node_modules && npm install`

**Permission errors:**
- Many system operations require root privileges
- Run backend with sudo: `sudo python3 main.py`
- Ensure proper file permissions for backup directories

**Database issues:**
- Reinitialize database: `python3 -c "from backup_db import init_db; init_db()"`
- Check SQLite file permissions
- Verify database path exists

### Logs and Debugging
- Backend logs: Check console output when running `sudo python3 main.py`
- Frontend logs: Check browser console and terminal output
- System logs: Use `journalctl` for system service logs
- Backup logs: Check `/var/log/` for backup operation logs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests if applicable
5. Commit your changes: `git commit -am 'Add feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request

### Development Guidelines
- Follow Python PEP 8 style guide for backend code
- Use TypeScript and follow React best practices for frontend
- Add proper error handling and logging
- Update documentation for new features
- Test changes thoroughly before submitting

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Next.js](https://nextjs.org/) - React framework for production
- [shadcn/ui](https://ui.shadcn.com/) - Beautiful UI components
- [Tailwind CSS](https://tailwindcss.com/) - Utility-first CSS framework
- [Radix UI](https://www.radix-ui.com/) - Low-level UI primitives

## 📞 Support

For support, please create an issue on GitHub or contact the development team.

---

**UpservX** - Simplifying server management with modern web technologies.