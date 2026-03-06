# Elasticsearch

Elasticsearch is a distributed, RESTful search and analytics engine built on Apache Lucene. It lets you store, search, and analyze large volumes of data in near real-time.

This setup includes **Kibana** for visual data exploration and dashboards.

## Components

| Container | Image | Purpose |
|---|---|---|
| `elasticsearch` | `elasticsearch:8.17.0` | Search & analytics engine |
| `elasticsearch-kibana` | `kibana:8.17.0` | Web UI for visualization and data exploration |

## Ports

| Port | Purpose |
|---|---|
| 9200 | Elasticsearch REST API |
| 5601 | Kibana web interface |

## Before You Start

**Change the password** – replace `changeme_strong_password` in both the `elasticsearch` and `kibana` service definitions in `docker-compose.yml`.

## Kibana First-Time Setup

After starting the containers, Kibana needs the `kibana_system` user password to be set. Run this once after Elasticsearch is healthy:

```bash
docker exec -it elasticsearch elasticsearch-reset-password \
  -u kibana_system --interactive
```

Enter the same password you set for `ELASTICSEARCH_PASSWORD` in the kibana service, then restart Kibana:

```bash
docker restart elasticsearch-kibana
```

## Accessing the Services

| Service | URL |
|---|---|
| Elasticsearch API | `http://<your-server-ip>:9200` |
| Kibana | `http://<your-server-ip>:5601` |

Default Kibana login:
- Username: `elastic`
- Password: the value of `ELASTIC_PASSWORD`

## System Requirements

Elasticsearch requires `vm.max_map_count` to be at least `262144`. Set it permanently on the host:

```bash
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

## Quick API Test

```bash
curl -u elastic:changeme_strong_password http://localhost:9200
```

## More Information

- [Elasticsearch Website](https://www.elastic.co/elasticsearch)
- [Kibana Website](https://www.elastic.co/kibana)
- [Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Docker Installation Guide](https://www.elastic.co/guide/en/elasticsearch/reference/current/docker.html)
