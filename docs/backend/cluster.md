# Cluster Management

**File:** `upservx-service/api/cluster.py` (2312 lines)

**Required permission:** Admin for configuration; signed cluster principal for inter-node communication

---

## Overview

Upcode Harbor supports a **master-child cluster** architecture. One instance acts as **master**, others as **child nodes**. The master manages all child nodes, aggregates their resources, and enables central management.

---

## Cluster Roles

| Role | Description |
|---|---|
| **Master** | Central instance; manages all child nodes; aggregates data |
| **Child Node** | Registers with the master; exposes its local API to the master |
| **Standalone** | No cluster configuration – default state |

---

## Configuration Files

| File | Description |
|---|---|
| `/etc/upservx/master` | Present if this instance is the master |
| `/etc/upservx/child` | Present if this instance is a child |
| `/etc/upservx/nodes/<id>.json` | Node info on the master (one file per child) |
| `/etc/upservx/cluster-security/` | Node-local CA, TLS certificate, and private keys |
| `/etc/upservx/cluster-nonces.json` | Persistent replay-protection cache |

### master config
```json
{
  "key": "random-secure-key",
  "key_id": "sha256-prefix",
  "previous_keys": [],
  "created_at": "2024-01-15T00:00:00Z",
  "cluster_name": "Main Cluster"
}
```

### child config
```json
{
  "master_ip": "master.example.com",
  "master_port": 9501,
  "cluster_key": "cluster-enrollment-key",
  "cluster_key_id": "sha256-prefix",
  "master_hostname": "master-1",
  "master_tls_ca": "-----BEGIN CERTIFICATE-----...",
  "assigned_hostname": "node-abc123"
}
```

### node entry (on master)
```json
{
  "hostname": "node-abc123",
  "ip_address": "10.0.0.12",
  "port": 9501,
  "tls_ca_certificate": "-----BEGIN CERTIFICATE-----...",
  "registered_at": "2024-01-15T12:00:00Z",
  "resources": {}
}
```

---

## Node Registration

```
1. Admin creates a cluster on the master: `POST /cluster/create`.
2. The create response returns the enrollment token once. `/cluster/info` never returns it.
3. The child bootstraps and pins the master's CA over HTTPS, then registers:
   `POST /cluster/join`
   {
     "master_ip": "10.0.0.10",
     "port": 9501,
     "token": "join-token"
   }
4. The master pins the child's CA in `/etc/upservx/nodes/<id>.json`.
5. The child pins the master's CA in `/etc/upservx/child`.
```

---

## Data Aggregation

The master proxies all API calls to the children:

```
GET /containers
→ Signed and sent to: https://child:9501/containers
```

This allows the master UI to display containers, VMs, metrics, etc. from all nodes centrally.

## Transport Security

- Inter-node traffic uses the dedicated HTTPS listener on port `9501`; client helpers reject non-HTTPS URLs.
- Every request is signed with HMAC-SHA256 over the method, raw path and query, body digest, sender identity, key ID, timestamp, and nonce.
- Requests outside the configured clock window or with a reused nonce are rejected. Nonces are protected by a file lock so replay checks work across workers.
- Each peer CA is obtained through a nonce-bound, HMAC-proven bootstrap response and then pinned for subsequent TLS connections.
- The master can rotate the cluster key with `POST /cluster/keys/rotate`. Current and previous keys overlap for a bounded period so nodes can transition without accepting expired keys.
- Legacy `Authorization: Bearer <cluster-key>` authentication is rejected.

---

## API Endpoints

### Cluster Management (Master)
| Method | Path | Description |
|---|---|---|
| `POST` | `/cluster/create` | Initialize this instance as master and return the enrollment token once |
| `GET` | `/cluster/info` | Cluster status without secrets |
| `GET` | `/cluster/nodes` | All registered nodes |
| `DELETE` | `/cluster/nodes/{id}` | Remove node |
| `POST` | `/cluster/keys/rotate` | Rotate the cluster key with a bounded overlap window |

### Node Registration (Child)
| Method | Path | Description |
|---|---|---|
| `POST` | `/cluster/join` | Bootstrap TLS and register as child node |
| `POST` | `/cluster/register` | Signed internal registration transport |
| `POST` | `/cluster/leave` | Leave the cluster |
| `GET` | `/cluster/info` | This node's cluster info |

### Internal Transport
| Method | Path | Description |
|---|---|---|
| `POST` | `/cluster/bootstrap` | Return the node CA with a nonce-bound proof |
| `GET` | `/cluster/node/metrics` | Child metrics |
| `POST` | `/cluster/ha/heartbeat` | HA heartbeat |
| `GET` | `/cluster/ha/vote` | Election vote |
| `POST` | `/cluster/keys/update` | Install a master-distributed rotated key |

### Replication Export/Import
| Method | Path | Description |
|---|---|---|
| `POST` | `/cluster/export/{resource_type}/{resource_name}` | Export a container or VM |
| `GET` | `/cluster/download/{filename}` | Download an exported archive |
| `POST` | `/cluster/upload` | Upload a raw signed archive |
| `POST` | `/cluster/import/{resource_type}` | Import an uploaded archive |

---

## Load Balancer Integration

The cluster module integrates with `load_balancer.py`:

- Distributes new container deployments across nodes
- Routes based on available CPU/RAM on each node
- Supports "least loaded" and "round-robin" strategies
