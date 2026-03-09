Docker Registry is a stateless, lightweight server-side application that stores and distributes Docker images. This template deploys the official **Registry v2** alongside **Docker Registry UI** for easy browser-based image management.

## Features

- 🗃️ Private container image storage
- ⚡ Lightweight and fast
- 🔒 Optional basic authentication (htpasswd)
- 🖥️ Web UI for browsing images and tags
- 🗑️ Image deletion via UI
- 🔄 Compatible with all Docker clients and CI/CD tools
- 📦 OCI image format support
- 🔌 Integrates with Traefik, GitLab CI, GitHub Actions, and more

## Access

| Service | URL |
|---|---|
| Registry API | `http://localhost:5000` |
| Registry UI | `http://localhost:8085` |

## Using the Registry

### Push an image

```bash
# Tag your image for the local registry
docker tag myimage:latest localhost:5000/myimage:latest

# Push it
docker push localhost:5000/myimage:latest
```

### Pull an image

```bash
docker pull localhost:5000/myimage:latest
```

### List all repositories

```bash
curl http://localhost:5000/v2/_catalog
```

### List tags for an image

```bash
curl http://localhost:5000/v2/myimage/tags/list
```

## Enable Basic Authentication

1. Generate an `htpasswd` file:

```bash
mkdir -p /opt/upservx/data/registry/auth
docker run --rm --entrypoint htpasswd httpd:2 \
  -Bbn myuser mysecretpassword \
  > /opt/upservx/data/registry/auth/htpasswd
```

2. Uncomment the auth environment variables in `docker-compose.yml`:

```yaml
- REGISTRY_AUTH=htpasswd
- REGISTRY_AUTH_HTPASSWD_REALM=Registry Realm
- REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd
```

3. Restart the registry:

```bash
docker compose restart registry
```

4. Log in via Docker CLI:

```bash
docker login localhost:5000
```

## Custom Configuration File

Place a `config.yml` in `/opt/upservx/data/registry/config/` for full control:

```yaml
version: 0.1
log:
  level: info
storage:
  filesystem:
    rootdirectory: /var/lib/registry
  delete:
    enabled: true
http:
  addr: 0.0.0.0:5000
  secret: changeme_registry_secret
health:
  storagedriver:
    enabled: true
    interval: 10s
    threshold: 3
```

## Behind a Reverse Proxy (Traefik / Nginx)

When using Traefik, add labels to the registry service:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.registry.rule=Host(`registry.example.com`)"
  - "traefik.http.routers.registry.entrypoints=websecure"
  - "traefik.http.routers.registry.tls.certresolver=letsencrypt"
  - "traefik.http.services.registry.loadbalancer.server.port=5000"
```

For Docker clients to push/pull over HTTPS without TLS warnings, configure a proper certificate. For HTTP-only (insecure), add to `/etc/docker/daemon.json` on each client:

```json
{
  "insecure-registries": ["registry.example.com:5000"]
}
```

## Allow Insecure Registry (local testing)

On each Docker host that uses this registry, add to `/etc/docker/daemon.json`:

```json
{
  "insecure-registries": ["localhost:5000"]
}
```

Then restart Docker: `sudo systemctl restart docker`

## Integration with GitLab CI

```yaml
# .gitlab-ci.yml
build:
  script:
    - docker build -t localhost:5000/myapp:$CI_COMMIT_SHORT_SHA .
    - docker push localhost:5000/myapp:$CI_COMMIT_SHORT_SHA
```

## Official Resources

- Docker Registry Docs: https://docs.docker.com/registry/
- Registry Image: https://hub.docker.com/_/registry
- Registry UI: https://github.com/Joxit/docker-registry-ui
- Registry API spec: https://docs.docker.com/registry/spec/api/

## Notes

- All images are persisted in `/opt/upservx/data/registry/data/`
- Change `REGISTRY_HTTP_SECRET` to a unique random string before deployment
- The Registry UI is configured to proxy API calls through Nginx — no CORS issues
- Image deletion via the UI requires `REGISTRY_STORAGE_DELETE_ENABLED=true` (enabled by default in this setup via the UI's delete capability)
- For production, enable authentication and use HTTPS via a reverse proxy
- Pairs well with Traefik (HTTPS), GitLab (CI/CD), and Harbor (if more features like scanning are needed)
