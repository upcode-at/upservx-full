Prometheus is an open-source systems monitoring and alerting toolkit originally built at SoundCloud. It is now a standalone open-source project and maintained independently of any company.

## Features

- 📊 Multi-dimensional data model
- 🔍 Powerful query language (PromQL)
- 📈 Time series collection via pull model
- 🎯 Service discovery
- 🔔 Flexible alerting
- 📉 Built-in visualization
- 💾 Efficient storage
- 🌐 HTTP pull model
- 📝 Client libraries
- 🔄 Push gateway support
- 🎨 Grafana integration
- 📡 Exporters ecosystem

## Default Configuration

- **Port**: 9090
- **Data Path**: /prometheus
- **Config Path**: /etc/prometheus

## Access

Web UI: `http://localhost:9090`

## Basic Configuration

Create `/opt/upservx/data/prometheus/config/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

## Official Resources

- Website: https://prometheus.io/
- Documentation: https://prometheus.io/docs/
- Exporters: https://prometheus.io/docs/instrumenting/exporters/
- Community: https://prometheus.io/community/

## Notes

- Configuration file required in config directory
- Use with Grafana for advanced visualization
- Exporters available for many applications
- AlertManager for managing alerts
