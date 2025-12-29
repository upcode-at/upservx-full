Redis is an open-source, in-memory data structure store used as a database, cache, message broker, and streaming engine. It supports various data structures such as strings, hashes, lists, sets, and more.

## Features

- ⚡ In-memory performance
- 💾 Optional persistence
- 🔄 Replication support
- 🎯 Pub/Sub messaging
- 📊 Rich data structures
- 🔐 Lua scripting
- 🌐 Clustering support
- 📈 Transactions
- 🔍 Pattern matching
- 🎨 Modules ecosystem
- 📝 Streams support
- 🚀 Sub-millisecond latency

## Default Configuration

- **Password**: redispassword
- **Port**: 6379
- **Persistence**: AOF enabled

## Connection Example

```bash
redis-cli -h localhost -p 6379 -a redispassword
```

## Connection String

```
redis://:redispassword@localhost:6379
```

## Official Resources

- Website: https://redis.io/
- Documentation: https://redis.io/docs/
- Commands: https://redis.io/commands/
- Community: https://redis.io/community/
