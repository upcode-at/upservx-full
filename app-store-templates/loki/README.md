Grafana Loki is a horizontally scalable, highly available, multi-tenant log aggregation system inspired by Prometheus. Unlike other logging systems, Loki is built around the idea of only indexing metadata about your logs (labels), and leaving the original log messages unindexed and compressed.

## Features

- 🪵 Efficient log aggregation
- 🏷️ Label-based indexing (similar to Prometheus)
- 💾 Cost-effective storage (only metadata indexed)
- 🔗 Native Grafana integration
- 📦 LogQL query language
- 🔄 Multi-tenancy support
- ⚡ High performance ingestion
- 🛠️ Promtail agent support
- 🌐 HTTP API
- 🔔 Alerting via Alertmanager

## Access

- **API / HTTP endpoint**: `http://localhost:3100`
- **Health check**: `http://localhost:3100/ready`

## Configuration

On first run, place your `loki-config.yml` into `/opt/upcode-harbor/data/loki/config/`. A minimal configuration example:

```yaml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1

schema_config:
  configs:
    - from: 2020-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/index_cache
  filesystem:
    directory: /loki/chunks

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h

chunk_store_config:
  max_look_back_period: 0s

table_manager:
  retention_deletes_enabled: false
  retention_period: 0s
```

## Integration with Grafana

1. Open Grafana → Configuration → Data Sources
2. Add a new data source of type **Loki**
3. Set the URL to `http://loki:3100` (if running in the same Docker network) or `http://localhost:3100`
4. Click **Save & Test**

## Log Shipping

Use **Promtail** as a log shipping agent to send logs to Loki:

```yaml
# promtail-config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: system
    static_configs:
      - targets:
          - localhost
        labels:
          job: varlogs
          __path__: /var/log/*log
```

## Official Resources

- Website: https://grafana.com/oss/loki/
- Documentation: https://grafana.com/docs/loki/latest/
- GitHub: https://github.com/grafana/loki
- LogQL: https://grafana.com/docs/loki/latest/logql/

## Notes

- Loki does **not** index log content by default — use LogQL to filter by labels
- For production use, consider object storage (S3, GCS) instead of the local filesystem
- Pair with Grafana for full log visualization and Promtail for log collection
