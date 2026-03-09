GitLab is a complete, open-source DevSecOps platform delivered as a single application. It covers the entire software development lifecycle: Git repository management, CI/CD pipelines, container registry, package registry, security scanning, issue tracking, wikis, and much more.

## Features

- 🦊 Git repository management with merge requests & code review
- 🔄 Built-in CI/CD pipelines (GitLab Runners)
- 📦 Container & package registry
- 🔍 Security scanning (SAST, DAST, dependency scanning)
- 🐛 Issue tracking & project management
- 📋 Wikis & documentation
- 🔑 SSH key management
- 👥 LDAP / OIDC / SAML authentication
- 🌐 Pages (static site hosting)
- 🔔 Webhooks & integrations
- 🛡️ Fine-grained access control

## Access

- **Web UI**: `http://localhost`
- **SSH**: `ssh://git@localhost:22`

## Default Credentials

- **Username**: root
- **Password**: Retrieved on first start (see below)

### Get the initial root password

```bash
docker exec -it gitlab grep 'Password:' /etc/gitlab/initial_root_password
```

> This file is deleted after 24 hours. Change the password immediately after first login.

## Configuration

All configuration is done via `GITLAB_OMNIBUS_CONFIG` or by editing `/opt/upservx/data/gitlab/config/gitlab.rb` directly, then running:

```bash
docker exec -it gitlab gitlab-ctl reconfigure
```

### Set a custom external URL

```ruby
external_url 'https://gitlab.example.com'
```

### Enable HTTPS with Let's Encrypt

```ruby
external_url 'https://gitlab.example.com'
letsencrypt['enable'] = true
letsencrypt['contact_emails'] = ['your@email.com']
```

### SMTP (Email)

```ruby
gitlab_rails['smtp_enable'] = true
gitlab_rails['smtp_address'] = "smtp.example.com"
gitlab_rails['smtp_port'] = 587
gitlab_rails['smtp_user_name'] = "user@example.com"
gitlab_rails['smtp_password'] = "yourpassword"
gitlab_rails['smtp_domain'] = "example.com"
gitlab_rails['smtp_authentication'] = "login"
gitlab_rails['smtp_enable_starttls_auto'] = true
gitlab_rails['gitlab_email_from'] = 'gitlab@example.com'
```

### Memory Tuning (low-resource servers)

```ruby
puma['worker_processes'] = 2
sidekiq['concurrency'] = 10
prometheus_monitoring['enable'] = false
```

## GitLab Runner

To enable CI/CD pipelines, deploy a GitLab Runner and register it:

```bash
docker run -d --name gitlab-runner --restart always \
  -v /opt/upservx/data/gitlab-runner/config:/etc/gitlab-runner \
  -v /var/run/docker.sock:/var/run/docker.sock \
  gitlab/gitlab-runner:latest

docker exec -it gitlab-runner gitlab-runner register
# Enter your GitLab URL and registration token from:
# GitLab → Admin → CI/CD → Runners
```

## Backup & Restore

### Create a backup

```bash
docker exec -t gitlab gitlab-backup create
# Backup stored in /var/opt/gitlab/backups inside the container
# = /opt/upservx/data/gitlab/data/backups on the host
```

### Restore a backup

```bash
docker exec -it gitlab gitlab-backup restore BACKUP=<timestamp>_<version>
```

## OIDC Integration (e.g. Keycloak)

Edit `gitlab.rb`:

```ruby
gitlab_rails['omniauth_enabled'] = true
gitlab_rails['omniauth_providers'] = [
  {
    name: 'openid_connect',
    label: 'Keycloak',
    args: {
      name: 'openid_connect',
      scope: ['openid', 'profile', 'email'],
      response_type: 'code',
      issuer: 'https://keycloak.example.com/realms/myrealm',
      client_auth_method: 'query',
      discovery: true,
      uid_field: 'preferred_username',
      client_options: {
        identifier: 'gitlab',
        secret: 'your-client-secret',
        redirect_uri: 'https://gitlab.example.com/users/auth/openid_connect/callback'
      }
    }
  }
]
```

## Official Resources

- Website: https://gitlab.com/
- Documentation: https://docs.gitlab.com/
- Docker Hub: https://hub.docker.com/r/gitlab/gitlab-ce
- GitHub Mirror: https://github.com/gitlabhq/gitlabhq

## Notes

- GitLab requires at least **4 GB RAM** (8 GB recommended for comfortable use)
- First startup takes **3–5 minutes** while Omnibus configures all services
- Port 22 maps SSH — if your host already uses port 22, change the host-side port (e.g. `"2222:22"`) and adjust `gitlab_shell_ssh_port` accordingly
- All data persists in `/opt/upservx/data/gitlab/`
- Pairs well with Harbor (container registry), Keycloak (SSO), and Traefik (reverse proxy)
