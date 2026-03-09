Keycloak is an open-source Identity and Access Management (IAM) solution. It provides single sign-on (SSO), user federation, identity brokering, and fine-grained authorization — ready to use out of the box.

## Features

- 🔑 Single Sign-On (SSO) & Single Logout
- 🌐 Social login (Google, GitHub, Facebook, etc.)
- 👥 User federation (LDAP, Active Directory)
- 🔒 Fine-grained authorization
- 📋 OpenID Connect, OAuth 2.0 & SAML 2.0 support
- 🛡️ Two-factor authentication (TOTP, WebAuthn)
- 🎨 Customizable login pages & themes
- 🔄 Identity brokering
- 📊 Admin console & account management
- 🔌 Extensible via SPIs

## Access

- **Admin Console**: `http://localhost:8080/admin`
- **Account Console**: `http://localhost:8080/realms/master/account`

## Default Credentials

- **Username**: admin
- **Password**: admin

> Change the admin password immediately after first login.

## Configuration

### Hostname

For production, set `KC_HOSTNAME` to your domain:

```env
KC_HOSTNAME=auth.example.com
```

### Behind a Reverse Proxy (e.g. Traefik/Nginx)

Set the following environment variables:

```env
KC_PROXY=edge
KC_HTTP_ENABLED=true
KC_HOSTNAME_STRICT=false
```

### Using start-dev (development mode)

Replace the `command` in docker-compose.yml with:

```yaml
command: start-dev
```

This skips hostname checks and uses an embedded H2 database — **not suitable for production**.

## Creating a Realm

1. Log in to the Admin Console
2. Click **Create Realm**
3. Enter a name and click **Create**
4. Configure clients, users, and roles for your application

## Connecting an Application (OIDC)

1. Go to your realm → **Clients** → **Create client**
2. Choose **OpenID Connect**
3. Set the **Valid redirect URIs** to your application URL
4. Use the generated **Client ID** and **Client Secret** in your app

## Official Resources

- Website: https://www.keycloak.org/
- Documentation: https://www.keycloak.org/documentation
- GitHub: https://github.com/keycloak/keycloak
- Docker Hub: https://quay.io/repository/keycloak/keycloak

## Notes

- This setup uses **PostgreSQL** as the database backend (recommended for production)
- Keycloak requires a healthy database before starting — the `depends_on` healthcheck handles this
- For production, use HTTPS and set `KC_HOSTNAME` to your actual domain
- Realm and client data are persisted in `/opt/upservx/data/keycloak/data`
