Traefik is a modern HTTP reverse proxy and load balancer designed for deploying microservices. It integrates natively with Docker and automatically discovers services, making configuration nearly zero-effort.

## Features

- 🔀 Automatic service discovery via Docker labels
- 🔒 Automatic SSL/TLS with Let's Encrypt
- 📊 Built-in web dashboard
- ⚖️ Load balancing (round-robin, sticky sessions, etc.)
- 🔌 Middleware support (auth, rate limiting, headers, redirects)
- 📜 Multiple configuration providers (Docker, file, Kubernetes)
- 🔔 Health checks & circuit breakers
- 📈 Metrics export (Prometheus, InfluxDB)
- 🌐 HTTP/2 and gRPC support
- 🔄 Zero-downtime reloads

## Access

- **Dashboard**: `http://localhost:8080/dashboard/`
- **HTTP**: `http://localhost:80`
- **HTTPS**: `https://localhost:443`

## Configuration

Traefik can be configured via environment variables (as set above) or a static config file. Place `traefik.yml` in `/opt/upcode-harbor/data/traefik/config/`:

```yaml
# traefik.yml
api:
  dashboard: true
  insecure: true

entryPoints:
  web:
    address: ":80"
  websecure:
    address: ":443"

providers:
  docker:
    exposedByDefault: false
  file:
    directory: /etc/traefik/dynamic
    watch: true

log:
  level: INFO

# Optional: Let's Encrypt
certificatesResolvers:
  letsencrypt:
    acme:
      email: your@email.com
      storage: /acme/acme.json
      httpChallenge:
        entryPoint: web
```

## Exposing a Service via Docker Labels

Add these labels to any container to route traffic through Traefik:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.myapp.rule=Host(`myapp.example.com`)"
  - "traefik.http.routers.myapp.entrypoints=websecure"
  - "traefik.http.routers.myapp.tls.certresolver=letsencrypt"
  - "traefik.http.services.myapp.loadbalancer.server.port=8080"
networks:
  - traefik_proxy
```

## HTTP to HTTPS Redirect

Add a dynamic config file at `/opt/upcode-harbor/data/traefik/config/dynamic/redirect.yml`:

```yaml
http:
  middlewares:
    redirect-to-https:
      redirectScheme:
        scheme: https
        permanent: true
  routers:
    http-catchall:
      rule: "HostRegexp(`{host:.+}`)"
      entryPoints:
        - web
      middlewares:
        - redirect-to-https
      service: noop
  services:
    noop:
      loadBalancer:
        servers: []
```

## Official Resources

- Website: https://traefik.io/
- Documentation: https://doc.traefik.io/traefik/
- GitHub: https://github.com/traefik/traefik
- Community: https://community.traefik.io/

## Notes

- The Docker socket mount (`/var/run/docker.sock`) is required for automatic service discovery
- For production, disable `api.insecure` and protect the dashboard with middleware (e.g., BasicAuth or ForwardAuth)
- Ensure the `acme.json` file has permissions `600` when using Let's Encrypt: `chmod 600 /opt/upcode-harbor/data/traefik/acme/acme.json`
- All services that should be routed through Traefik must share the same Docker network (`traefik_proxy`)
