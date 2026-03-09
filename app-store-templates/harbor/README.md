Harbor is an open-source, enterprise-grade container image registry. It extends the open-source Docker Distribution by adding features such as role-based access control, image vulnerability scanning, content trust/signing, audit logging, and replication across registries.

## Features

- ⚓ Private container image registry
- 🔐 Role-based access control (RBAC)
- 🔍 Image vulnerability scanning (Trivy / Clair)
- ✍️ Content signing & trust (Notation / Cosign)
- 🔄 Cross-registry replication
- 📋 Audit logging
- 🪣 Multi-tenancy via projects
- 🌐 OIDC / LDAP / AD integration
- 📊 Web UI & REST API
- 🏷️ OCI artifact support (Helm charts, OPA policies, etc.)

## Access

- **Web UI**: `http://localhost:80` or `https://localhost:443`

## Default Credentials

- **Username**: admin
- **Password**: Harbor12345

> Change the admin password immediately after first login via **Administration → Users**.

## Recommended: Official Installer

Harbor is best deployed using the official installer, which generates a fully configured `docker-compose.yml` and all required config files:

```bash
# Download the latest offline installer
wget https://github.com/goharbor/harbor/releases/latest/download/harbor-offline-installer.tgz
tar xzvf harbor-offline-installer.tgz
cd harbor

# Copy and edit the config
cp harbor.yml.tmpl harbor.yml
# Edit harbor.yml: set hostname, admin password, DB password, storage path

# Run the installer
sudo ./install.sh
```

## Configuration: harbor.yml (key settings)

```yaml
hostname: registry.example.com

http:
  port: 80

https:
  port: 443
  certificate: /your/cert.crt
  private_key: /your/key.key

harbor_admin_password: YourSecurePassword

database:
  password: YourDBPassword

data_volume: /opt/upservx/data/harbor/data
```

## Logging in via Docker CLI

```bash
docker login localhost
# Username: admin
# Password: Harbor12345

# Tag and push an image
docker tag myimage:latest localhost/myproject/myimage:latest
docker push localhost/myproject/myimage:latest
```

## Image Scanning

1. Go to **Administration → Interrogation Services**
2. Enable **Trivy** scanner
3. Configure projects to scan images on push: **Project → Configuration → Automatically scan images on push**

## OIDC / SSO Integration (e.g. Keycloak)

1. Go to **Administration → Configuration → Authentication**
2. Set **Auth Mode** to **OIDC Provider**
3. Enter your OIDC endpoint, Client ID, and Client Secret

## Official Resources

- Website: https://goharbor.io/
- Documentation: https://goharbor.io/docs/
- GitHub: https://github.com/goharbor/harbor
- Releases: https://github.com/goharbor/harbor/releases

## Notes

- The compose file in this template uses Harbor `v2.11.0` images — update the image tags to match your desired release
- For production, use the official installer for a fully pre-configured setup
- All persistent data is stored under `/opt/upservx/data/harbor/`
- Change `CORE_SECRET` and `JOBSERVICE_SECRET` to unique random strings before deployment
- Harbor pairs excellently with Keycloak (OIDC SSO) and Trivy (vulnerability scanning)
