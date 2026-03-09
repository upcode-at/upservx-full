OpenLDAP is a free, open-source implementation of the Lightweight Directory Access Protocol (LDAP). It provides a centralized directory for managing users, groups, and authentication across your entire infrastructure — from Linux systems to web applications.

This template includes **phpLDAPadmin** as a web-based management UI.

## Features

- 📒 Centralized user & group management
- 🔐 Authentication backend for many applications
- 🌐 LDAP (port 389) and LDAPS (port 636) support
- 🔄 Replication support
- 🏷️ Flexible schema system
- 🔌 Integrates with Keycloak, GitLab, Grafana, Nextcloud, and more
- 🛡️ Access control lists (ACLs)
- 🖥️ phpLDAPadmin web UI included

## Access

| Service | URL |
|---|---|
| LDAP (plaintext) | `ldap://localhost:389` |
| LDAPS (TLS) | `ldaps://localhost:636` |
| phpLDAPadmin UI | `http://localhost:8090` |

## Default Credentials

### LDAP Admin

- **Bind DN**: `cn=admin,dc=example,dc=com`
- **Password**: `admin`

### phpLDAPadmin

- **Login DN**: `cn=admin,dc=example,dc=com`
- **Password**: `admin`

> Adjust `dc=example,dc=com` to match your `LDAP_DOMAIN` setting.

## Configuration

Set your domain and organisation via environment variables:

```env
LDAP_DOMAIN=example.com           # → dc=example,dc=com
LDAP_ORGANISATION=My Organisation
LDAP_ADMIN_PASSWORD=securepassword
```

After changing the domain, the base DN becomes `dc=example,dc=com`.

## Adding Users & Groups via ldif

### Add an Organizational Unit for users

```ldif
dn: ou=users,dc=example,dc=com
objectClass: organizationalUnit
ou: users
```

```bash
docker exec -it openldap ldapadd -x \
  -D "cn=admin,dc=example,dc=com" \
  -W -f users-ou.ldif
```

### Add a user

```ldif
dn: uid=jdoe,ou=users,dc=example,dc=com
objectClass: inetOrgPerson
objectClass: posixAccount
objectClass: shadowAccount
cn: John Doe
sn: Doe
uid: jdoe
uidNumber: 1001
gidNumber: 1001
homeDirectory: /home/jdoe
loginShell: /bin/bash
userPassword: {SSHA}hashedpassword
```

Generate a password hash:

```bash
docker exec -it openldap slappasswd -s mysecretpassword
```

## LDAP Search

```bash
# List all entries
docker exec -it openldap ldapsearch -x \
  -H ldap://localhost \
  -D "cn=admin,dc=example,dc=com" \
  -w admin \
  -b "dc=example,dc=com"
```

## Integrations

### Keycloak

1. Go to **User Federation → Add LDAP provider**
2. Set **Connection URL**: `ldap://openldap:389`
3. **Bind DN**: `cn=admin,dc=example,dc=com`
4. **Users DN**: `ou=users,dc=example,dc=com`

### GitLab (`gitlab.rb`)

```ruby
gitlab_rails['ldap_enabled'] = true
gitlab_rails['ldap_servers'] = {
  'main' => {
    'label' => 'LDAP',
    'host' =>  'openldap',
    'port' => 389,
    'uid' => 'uid',
    'bind_dn' => 'cn=admin,dc=example,dc=com',
    'password' => 'admin',
    'base' => 'ou=users,dc=example,dc=com',
    'encryption' => 'plain'
  }
}
```

### Grafana (`grafana.ini`)

```ini
[auth.ldap]
enabled = true
config_file = /etc/grafana/ldap.toml
```

```toml
[[servers]]
host = "openldap"
port = 389
use_ssl = false
bind_dn = "cn=admin,dc=example,dc=com"
bind_password = "admin"
search_filter = "(uid=%s)"
search_base_dns = ["ou=users,dc=example,dc=com"]
```

## Enable TLS (LDAPS)

Set in environment:

```env
LDAP_ENABLE_TLS=yes
LDAP_TLS_CERT_FILE=/opt/bitnami/openldap/certs/ldap.crt
LDAP_TLS_KEY_FILE=/opt/bitnami/openldap/certs/ldap.key
LDAP_TLS_CA_FILE=/opt/bitnami/openldap/certs/ca.crt
```

And mount your certificates into the container.

## Official Resources

- Website: https://www.openldap.org/
- Documentation: https://www.openldap.org/doc/
- Bitnami Image: https://hub.docker.com/r/bitnami/openldap
- phpLDAPadmin: https://phpldapadmin.sourceforge.net/

## Notes

- Data and schema are persisted in `/opt/upservx/data/openldap/`
- phpLDAPadmin is included for easy browser-based administration
- For production, enable TLS and use strong passwords
- When integrating with other services, use the container hostname `openldap` as the LDAP host (within the same Docker network)
- Pairs well with Keycloak (identity broker), GitLab, Grafana, and Nextcloud
