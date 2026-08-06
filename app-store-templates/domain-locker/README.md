# Domain Locker

Professional domain and DNS management platform with advanced security features to protect your domain portfolio.

## Features

- 🔐 Domain security and locking
- 🌐 DNS management with PowerDNS
- 🛡️ DNSSEC support
- 📊 Domain monitoring and alerts
- 👥 Multi-user access control
- 📝 Audit logging
- 🔄 Automatic DNS record updates
- 🔍 DNS query analytics

## Getting Started

1. Access Domain Locker at `http://your-server-ip:8081`
2. Default credentials:
   - Username: `admin`
   - Password: `changeme`
3. Change the default password immediately!
4. Configure your DNS zones and records

## Default Configuration

- **Web Port**: 8081
- **DNS Port**: 53 (TCP/UDP)
- **Admin User**: admin
- **Data Directory**: /opt/upcode-harbor/data/domain-locker
- **Database**: PostgreSQL 15

## Security Recommendations

1. Change `ADMIN_PASSWORD` in environment variables
2. Generate a strong `SECRET_KEY` (min. 32 characters)
3. Use HTTPS with a reverse proxy (nginx, traefik)
4. Enable 2FA for admin accounts
5. Regular backups of the database

## DNS Configuration

To use this as your DNS server:
- Point your domain registrar to this server's IP
- Configure NS records properly
- Ensure port 53 is open on your firewall

## Official Documentation

https://github.com/PowerDNS-Admin/PowerDNS-Admin
