# Jenkins

The leading open source automation server. Jenkins provides hundreds of plugins to support building, deploying and automating any project.

## Features

- 🔄 Continuous Integration and Continuous Delivery
- 🔌 1800+ plugins for integration with any tool
- 📋 Pipeline as Code with Jenkinsfile
- 🌐 Distributed builds across multiple machines
- 🔐 Role-based access control
- 📊 Rich visualization and reporting
- 🐳 Docker integration for containerized builds

## Getting Started

1. Access Jenkins at `http://your-server-ip:8080`
2. Get the initial admin password:
   ```bash
   docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
   ```
3. Follow the setup wizard to install plugins and create admin user
4. Start creating your first pipeline!

## Default Configuration

- **Web Port**: 8080
- **Agent Port**: 50000 (for build agents)
- **Data Directory**: /opt/upcode-harbor/data/jenkins
- **Docker Socket**: Mounted for Docker-in-Docker builds

## Important Notes

- The initial admin password is located at `/var/jenkins_home/secrets/initialAdminPassword`
- Docker socket is mounted to enable Docker builds from Jenkins
- Running as root for Docker access (adjust if needed for security)

## Official Documentation

https://www.jenkins.io/doc/
