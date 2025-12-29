Nginx Proxy Manager is a Docker container that provides an easy way to manage Nginx proxy hosts with a clean, efficient, and beautiful web interface.

## Features

- 🔒 Free SSL certificates from Let's Encrypt
- 🌐 Reverse proxy with custom locations
- 🚦 Stream forwarding (TCP/UDP)
- 🔐 Access lists and basic HTTP authentication
- 📊 Beautiful and secure admin interface
- 🎯 Support for multiple domains
- 📝 Custom Nginx configurations
- 🔄 Automatic certificate renewal
- 🛡️ Built-in security features
- 📱 Responsive design

## Quick Start

1. Access the admin interface at `http://your-server-ip:81`
2. Default login credentials:
   - **Email:** `admin@example.com`
   - **Password:** `changeme`
3. **IMPORTANT:** Change these credentials immediately after first login!

## Default Ports

- **80:** HTTP traffic
- **443:** HTTPS traffic
- **81:** Admin web interface

## Common Use Cases

### Reverse Proxy Setup
1. Add a Proxy Host in the admin panel
2. Enter your domain name
3. Configure the forward hostname/IP and port
4. Enable SSL with Let's Encrypt
5. Save and access your service via domain

### SSL Certificate
- Automatic Let's Encrypt certificate generation
- Auto-renewal before expiration
- Support for wildcard certificates
- Custom certificate upload

### Access Control
- Create access lists
- Set up basic authentication
- Control who can access your services
- IP-based restrictions

## Configuration

### DNS Requirements
For SSL certificates to work:
1. Your domain must point to your server's IP
2. Ports 80 and 443 must be accessible from the internet
3. Your router must forward these ports to your server

### Email Configuration
Set up email for Let's Encrypt notifications:
1. Go to Settings in admin panel
2. Configure SMTP settings
3. Test email delivery

## Security Best Practices

1. **Change default credentials immediately**
2. Use strong passwords
3. Enable 2FA if available
4. Keep the container updated
5. Use access lists for sensitive services
6. Regular backups of /data directory

## Backup

Important directories to backup:
- `/opt/upservx/data/nginx-proxy-manager/data` - Configuration and database
- `/opt/upservx/data/nginx-proxy-manager/letsencrypt` - SSL certificates

## Troubleshooting

### Certificate Issues
- Ensure ports 80/443 are open and forwarded
- Check DNS is correctly configured
- Verify domain points to correct IP

### Cannot Access Admin Panel
- Check if port 81 is accessible
- Verify container is running
- Check firewall rules

## Resource Usage

- **RAM:** ~100-200 MB
- **CPU:** Minimal
- **Disk:** ~50-100 MB + certificates

## Official Documentation

https://nginxproxymanager.com/
