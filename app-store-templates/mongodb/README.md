MongoDB is a source-available cross-platform document-oriented NoSQL database program. It uses JSON-like documents with optional schemas and is designed for scalability and developer agility.

## Features

- 📄 Document-oriented storage
- 🔍 Rich query language
- 📊 Aggregation framework
- 🔄 Horizontal scaling (sharding)
- 🎯 Indexing support
- 💾 GridFS for large files
- 🌐 Geospatial queries
- 🔐 Role-based access control
- 📈 Change streams
- 🚀 High performance
- 📝 Schema validation
- 🔄 Replication & high availability

## Default Credentials

- **Root Username**: admin
- **Root Password**: adminpassword
- **Database**: mydb
- **Port**: 27017

## Connection Example

```bash
mongosh "mongodb://admin:adminpassword@localhost:27017"
```

## Connection String

```
mongodb://admin:adminpassword@localhost:27017/mydb?authSource=admin
```

## Official Resources

- Website: https://www.mongodb.com/
- Documentation: https://docs.mongodb.com/
- University: https://university.mongodb.com/
- Community: https://www.mongodb.com/community/

## Notes

- Change default credentials in production environments
- Consider using MongoDB Compass for GUI management
- Regular backups with mongodump recommended
