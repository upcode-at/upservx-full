# Container Management

**File:** `upservx-service/containers.py`
**API sub-module:** `upservx-service/api/containers.py`

**Required permission:** `docker` group or `lxd`/`lxc` group (or admin)

---

## Overview

The container module supports three container runtimes:

| Runtime | CLI Tool | Detection |
|---|---|---|
| **Docker** | `docker` | `shutil.which("docker")` |
| **LXC / LXD** | `lxc` | `shutil.which("lxc")` |
| **Kubernetes** | `kubectl` | `shutil.which("kubectl")` |

---

## Data Model: `Container`

```python
class Container(BaseModel):
    id: int
    name: str
    type: str            # "Docker", "LXC", "Kubernetes"
    status: str          # "running", "stopped"
    image: str
    ports: List[str]
    mounts: List[str]
    envs: List[str]
    cpu: float
    memory: int
    created: str
```

---

## Functions

### Docker

| Function | Description |
|---|---|
| `get_docker_containers()` | Lists all Docker containers (`docker ps -a`) |
| `create_docker_container(...)` | Creates and starts a container (`docker run`) |
| `start_docker_container(name)` | Starts a container (`docker start`) |
| `stop_docker_container(name)` | Stops a container (`docker stop`) |
| `delete_docker_container(name)` | Deletes a container (`docker rm -f`) |
| `get_docker_logs(name)` | Returns the last 200 log lines |
| `get_docker_stats(name)` | Returns CPU/RAM statistics |

### LXC

| Function | Description |
|---|---|
| `get_lxc_containers()` | Lists all LXC containers (`lxc list --format json`) |
| `create_lxc_container(...)` | Creates an LXC container |
| `start_lxc_container(name)` | Starts an LXC container |
| `stop_lxc_container(name)` | Stops an LXC container |
| `delete_lxc_container(name)` | Deletes an LXC container |

### Kubernetes

| Function | Description |
|---|---|
| `get_k8s_pods()` | Lists all K8s pods (`kubectl get pods -A -o json`) |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/containers` | All containers (Docker + LXC + K8s) |
| `POST` | `/containers` | Create container |
| `POST` | `/containers/{name}/start` | Start container |
| `POST` | `/containers/{name}/stop` | Stop container |
| `DELETE` | `/containers/{name}` | Delete container |
| `GET` | `/containers/{name}/logs` | Container logs |
| `GET` | `/containers/{name}/stats` | CPU/RAM stats |
| `GET` | `/containers/{name}/inspect` | Detailed view |
| `GET` | `/containers/{name}/storage` | Volume information |
| `POST` | `/containers/{name}/exec` | Execute command in container |

---

## App Store Integration

App store functions are also in the container namespace:

| Method | Path | Description |
|---|---|---|
| `GET` | `/containers/app-store/apps` | Available apps |
| `GET` | `/containers/app-store/apps/{id}` | App details |
| `POST` | `/containers/app-store/apps/{id}/install` | Install app |
| `POST` | `/containers/app-store/apps/{id}/uninstall` | Uninstall app |
| `GET` | `/containers/app-store/apps/{id}/icon` | App icon (public) |

---

## Docker Compose Integration

| Method | Path | Description |
|---|---|---|
| `GET` | `/containers/compose` | Installed Compose projects |
| `POST` | `/containers/compose/{name}/up` | Start project |
| `POST` | `/containers/compose/{name}/down` | Stop project |

---

## Docker Volume Management

| Method | Path | Description |
|---|---|---|
| `GET` | `/containers/volumes` | All Docker volumes |
| `DELETE` | `/containers/volumes/{name}` | Delete volume |

---

## Images

Separate API under `api/images.py`:

| Method | Path | Description |
|---|---|---|
| `GET` | `/images` | All Docker/LXC images |
| `POST` | `/images/pull` | Pull image |
| `DELETE` | `/images/{id}` | Delete image |
| `POST` | `/images/build` | Build image (Dockerfile) |
