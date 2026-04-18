MinIO is a high-performance, S3-compatible object storage server designed for self-hosted deployments. It provides the same API as Amazon S3, making it compatible with any S3-aware application, backup tool, or SDK.

## Features

- 🪣 Amazon S3-compatible API
- ⚡ High-performance – optimized for large objects and throughput
- 🌐 Web Console for bucket and object management
- 🔑 Access key and secret key management
- 🔒 Server-side encryption (SSE-S3, SSE-KMS)
- 📋 Bucket policies, versioning, and lifecycle rules
- 🔔 Event notifications (webhooks, Kafka, NATS, Redis)
- 🔄 Works as a backend for Nextcloud, Gitea, Harbor, Loki, and more

## Default Access

| Service | URL |
|---|---|
| S3 API | `http://<your-server>:9000` |
| Web Console | `http://<your-server>:9001` |

Default credentials (change before use):
- **Username:** `admin`
- **Password:** `changeme-min-12-chars`

> ⚠️ The password must be at least 12 characters.

## Creating a Bucket

Via the web console or using the `mc` CLI:

```bash
# Install MinIO Client
docker run --rm -it --entrypoint=/bin/sh minio/mc

# Configure alias
mc alias set local http://<your-server>:9000 admin changeme-min-12-chars

# Create a bucket
mc mb local/my-bucket

# Upload a file
mc cp myfile.txt local/my-bucket/
```

## S3-Compatible Clients

Configure any S3 client with:
- **Endpoint:** `http://<your-server>:9000`
- **Access Key:** your `MINIO_ROOT_USER`
- **Secret Key:** your `MINIO_ROOT_PASSWORD`
- **Region:** `us-east-1` (or any value – MinIO accepts all)
- **Path-style access:** enabled

## Integration Examples

**Nextcloud** – use as external S3 primary storage or as backup target via the S3 backup app.

**Loki / Prometheus** – use as object storage backend for long-term metric and log retention.

**Restic / Duplicati** – use as S3-compatible backup destination.

## Data & Persistence

| Path | Description |
|---|---|
| `/opt/upservx/data/minio` | All bucket data and objects |

## Ports

| Port | Description |
|---|---|
| `9000` | S3 API endpoint |
| `9001` | Web Console |

## Official Documentation

https://min.io/docs/
