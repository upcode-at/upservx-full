# Portainer

Powerful container management made simple.

## Features

- 🐳 Docker container management
- ☸️ Kubernetes cluster management
- 🌐 Intuitive web interface
- 👥 Multi-user access control
- 📊 Resource monitoring
- 📋 Template library
- 🔐 Role-based access control

## Configuration

### Default Ports
- **9000**: Web interface (HTTP)
- **9443**: Web interface (HTTPS)

### Volumes
- `/data`: Portainer configuration and database
- `/var/run/docker.sock`: Docker socket (required for management)

## First Time Setup

1. Access Portainer at `https://your-server-ip:9443`
2. Create an admin account (must be done within 5 minutes of first start)
3. Choose "Docker" as the environment
4. Start managing your containers!

## Features

### Container Management
- Start, stop, restart containers
- View logs in real-time
- Execute commands inside containers
- Inspect container details

### Image Management
- Pull images from registries
- Build images from Dockerfiles
- Manage image tags

### Volume Management
- Create and delete volumes
- Browse volume contents
- Backup and restore

### Network Management
- Create custom networks
- Manage network connections

## Security

- Always use HTTPS (port 9443)
- Set a strong admin password
- Enable two-factor authentication
- Restrict access to trusted networks

## Official Documentation

https://docs.portainer.io/
