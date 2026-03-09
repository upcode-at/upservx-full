# Cluster Management

**File:** `upservx-service/api/cluster.py` (2312 lines)

**Required permission:** Admin for configuration; cluster token for inter-node communication

---

## Overview

UpservX supports a **master-child cluster** architecture. One instance acts as **master**, others as **child nodes**. The master manages all child nodes, aggregates their resources, and enables central management.

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
| `/etc/upservx/cluster_key` | Shared key for cluster authentication |

### master config
```json
{
  "key": "random-secure-key",
  "created_at": "2024-01-15T00:00:00Z",
  "name": "Main Cluster"
}
```

### child config
```json
{
  "master_url": "https://master.example.com:9500",
  "token": "cluster-node-token",
  "node_id": "node-abc123"
}
```

### node entry (on master)
```json
{
  "id": "node-abc123",
  "name": "Child Server 1",
  "url": "https://child1.example.com:9500",
  "token": "node-specific-token",
  "registered_at": "2024-01-15T12:00:00Z",
  "last_seen": "2024-01-15T14:30:00Z",
  "status": "online",
  "version": "0.2.0"
}
```

---

## Node Registration

```
1. Admin creates cluster on master: POST /cluster/init
2. Admin gets join token: GET /cluster/token
3. Child registers: POST /cluster/register
   {
     "master_url": "...",
     "token": "join-token",
     "node_name": "Child 1",
     "node_url": "https://child1:9500"
   }
4. Master writes /etc/upservx/nodes/<id>.json
5. Child writes /etc/upservx/child
```

---

## Data Aggregation

The master proxies all API calls to the children:

```
GET /cluster/nodes/{node_id}/containers
→ Proxied to: https://child:9500/containers
```

This allows the master UI to display containers, VMs, metrics, etc. from all nodes centrally.

---

## API Endpoints

### Cluster Management (Master)
| Method | Path | Description |
|---|---|---|
| `POST` | `/cluster/init` | Initialize this instance as master |
| `GET` | `/cluster/status` | Cluster status |
| `GET` | `/cluster/nodes` | All registered nodes |
| `DELETE` | `/cluster/nodes/{id}` | Remove node |
| `GET` | `/cluster/token` | Generate join token |

### Node Registration (Child)
| Method | Path | Description |
|---|---|---|
| `POST` | `/cluster/register` | Register as child node |
| `DELETE` | `/cluster/leave` | Leave the cluster |
| `GET` | `/cluster/info` | This node's cluster info |

### Data Proxy (Master → Child)
| Method | Path | Description |
|---|---|---|
| `GET` | `/cluster/nodes/{id}/containers` | Child containers |
| `GET` | `/cluster/nodes/{id}/vms` | Child VMs |
| `GET` | `/cluster/nodes/{id}/metrics` | Child metrics |
| `GET` | `/cluster/nodes/{id}/drives` | Child storage |

### Config Export/Import
| Method | Path | Description |
|---|---|---|
| `GET` | `/cluster/export` | Export cluster config |
| `POST` | `/cluster/import` | Import cluster config |
| `GET` | `/cluster/download` | Download config as file |
| `POST` | `/cluster/upload` | Upload config file |

---

## Load Balancer Integration

The cluster module integrates with `load_balancer.py`:

- Distributes new container deployments across nodes
- Routes based on available CPU/RAM on each node
- Supports "least loaded" and "round-robin" strategies
