# Virtual Machine Management

**File:** `upcode-harbor-service/vms.py`
**API sub-module:** `upcode-harbor-service/api/vms.py`

**Required permission:** `libvirt` or `kvm` group (or admin)

---

## Overview

Upcode Harbor manages virtual machines via `libvirt`/`virsh`. Both QEMU/KVM and other hypervisors supported by libvirt can be managed.

---

## Data Model: `VM`

```python
class VM(BaseModel):
    id: int
    uuid: str
    name: str
    status: str       # "running", "stopped", "paused"
    vcpus: int
    memory_mb: int
    disks: List[str]
    networks: List[str]
    created: str
```

---

## Core Functions

| Function | Description |
|---|---|
| `get_vms()` | Lists all VMs via `virsh list --all --name` |
| `get_vm_info(name)` | Detailed information (`virsh dominfo`, `virsh dumpxml`) |
| `start_vm(name)` | Starts a VM (`virsh start`) |
| `stop_vm(name)` | Graceful shutdown (`virsh shutdown`) |
| `force_stop_vm(name)` | Force shutdown (`virsh destroy`) |
| `reboot_vm(name)` | Reboot (`virsh reboot`) |
| `pause_vm(name)` | Pause VM (`virsh suspend`) |
| `resume_vm(name)` | Resume (`virsh resume`) |
| `delete_vm(name)` | Delete VM with all disk images |
| `get_vm_stats(name)` | CPU and memory stats |
| `create_vm(...)` | Create new VM (ISO, network, disk size) |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/vms` | All virtual machines |
| `POST` | `/vms` | Create new VM |
| `GET` | `/vms/{name}` | VM details |
| `DELETE` | `/vms/{name}` | Delete VM |
| `POST` | `/vms/{name}/start` | Start VM |
| `POST` | `/vms/{name}/stop` | Graceful stop |
| `POST` | `/vms/{name}/force-stop` | Force stop |
| `POST` | `/vms/{name}/reboot` | Reboot |
| `POST` | `/vms/{name}/pause` | Pause |
| `POST` | `/vms/{name}/resume` | Resume |
| `GET` | `/vms/{name}/stats` | CPU/RAM stats |
| `GET` | `/vms/{name}/vnc` | VNC connection info |
| `WebSocket` | `/vms/{name}/vnc/ws` | VNC WebSocket proxy |

---

## ISO Management

**File:** `upcode-harbor-service/isos.py`

| Method | Path | Description |
|---|---|---|
| `GET` | `/isos` | All available ISO files |
| `POST` | `/isos/upload` | Upload an ISO file |
| `DELETE` | `/isos/{filename}` | Delete ISO file |
| `GET` | `/isos/{filename}/file` | Download ISO (public) |

ISOs are stored in `/var/lib/libvirt/images/` by default.

---

## VNC Integration

| Component | Description |
|---|---|
| VNC port | Determined via `virsh dumpxml` → `<graphics type='vnc' port='...'/>` |
| WS Proxy | Upcode Harbor acts as a WebSocket proxy to the local VNC port |
| Token | WS ticket required before connection |

VNC sessions are proxied through the backend. The raw VNC port is not exposed directly.
