# Paperless-ngx

A community-supported supercharged version of paperless: scan, index and archive all your physical documents.

## Features

- 📄 **Document Management**: Organize and search your documents
- 🔍 **OCR**: Automatic text recognition in multiple languages
- 🏷️ **Tagging & Classification**: Organize with tags, correspondents, and document types
- 📧 **Email Import**: Automatically import documents from email
- 🔄 **Automatic Processing**: Watch folder for automatic document intake
- 📱 **Mobile App**: iOS and Android apps available
- 🌐 **REST API**: Full API access for integrations
- 📊 **Advanced Search**: Full-text search with filters
- 📦 **Bulk Operations**: Process multiple documents at once

## Initial Setup

1. **Generate Secret Key**:
   ```bash
   openssl rand -base64 32
   ```
   Use this value for `PAPERLESS_SECRET_KEY`

2. **Configure Environment**:
   - Set `PAPERLESS_URL` to your public URL
   - Set `PAPERLESS_TIME_ZONE` to your timezone
   - Configure `PAPERLESS_OCR_LANGUAGE` for your languages
   - Set admin credentials

3. **Start Services**:
   ```bash
   docker-compose up -d
   ```

4. **Access Web Interface**:
   - URL: http://your-server:8000
   - Login with configured admin credentials

## Usage

### Document Import

1. **Consume Directory**:
   - Place documents in `./consume` directory
   - They will be automatically processed and moved

2. **Web Upload**:
   - Use the web interface to upload documents
   - Drag and drop supported

3. **Email Import**:
   - Configure email settings in the admin panel
   - Documents can be sent via email

### OCR Languages

Configure `PAPERLESS_OCR_LANGUAGE` with language codes:
- `eng` - English
- `deu` - German
- `fra` - French
- `spa` - Spanish
- `ita` - Italian
- Multiple languages: `deu+eng` or `fra+eng+deu`

Install additional languages via the admin panel if needed.

## Configuration

### Environment Variables

- `PAPERLESS_SECRET_KEY`: Encryption key (required, generate random string)
- `PAPERLESS_URL`: Public URL for the application
- `PAPERLESS_TIME_ZONE`: Application timezone
- `PAPERLESS_OCR_LANGUAGE`: OCR language codes
- `PAPERLESS_ADMIN_USER`: Initial admin username
- `PAPERLESS_ADMIN_PASSWORD`: Initial admin password
- `PAPERLESS_ADMIN_MAIL`: Admin email address

### Database

- PostgreSQL 16 is included in the stack
- Database data persisted in `pgdata` volume
- Automatic backup recommended

### Redis

- Redis is used for task queuing
- Data persisted in `redisdata` volume

## Volumes

- `data`: Application data and indexes
- `media`: Stored documents (encrypted)
- `export`: Export directory for bulk exports
- `consume`: Document intake directory

## Backup

Important directories to backup:
- `data` volume (application data)
- `media` volume (documents)
- `pgdata` volume (database)

## Mobile Apps

- **Android**: Available on Google Play
- **iOS**: Available on App Store

Configure the `PAPERLESS_URL` correctly for mobile access.

## Advanced Features

### Workflows

- Automatic tagging based on content
- Document routing based on correspondents
- Custom processing rules

### API Access

- Full REST API available
- Documentation at `/api/docs/`
- Use for custom integrations

### Email Integration

1. Configure email settings in admin panel
2. Send documents to configured email address
3. Subject line can set tags and metadata

## Troubleshooting

### OCR Not Working

- Check OCR language configuration
- Verify language packs are installed
- Check container logs

### Documents Not Processing

- Check consume directory permissions
- Verify Redis connection
- Check worker logs

### Performance Issues

- Increase memory allocation
- Add more CPU cores
- Consider SSD for document storage

## Resources

- **Documentation**: https://docs.paperless-ngx.com/
- **GitHub**: https://github.com/paperless-ngx/paperless-ngx
- **Community Forum**: https://github.com/paperless-ngx/paperless-ngx/discussions

## Security Notes

- Change default admin password immediately
- Use strong `PAPERLESS_SECRET_KEY`
- Enable HTTPS for production use
- Regular backups recommended
- Keep software updated
