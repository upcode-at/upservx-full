# Storage Management

**File:** `upcode-harbor-service/storage.py`
**API sub-module:** `upcode-harbor-service/api/storage.py`

**Required permission:** `disk` or `storage` group (or admin)

---

## Overview

The storage module manages:

- **Physical drives** (HDD, SSD – NVMe, SATA)
- **Partitions**
- **Mounted filesystems**
- **ZFS pools** (if ZFS is available)

---

## Physical Drives

### Data per Drive

```python
class Drive(BaseModel):
    name: str             # e.g. "sda", "nvme0n1"
    model: str
    vendor: str
    size_bytes: int
    type: str             # "HDD", "SSD", "NVMe"
    rotational: bool
    partitions: List[Partition]
    temperature: int      # °C (if available)
    smart_status: str     # "OK", "FAIL", "UNKNOWN"
```

Data is read via:
- `/proc/partitions` and `/sys/block/*/` for basic info
- `lsblk -J` for partition tree
- `smartctl -j -a /dev/<device>` for SMART data and temperature

---

## Partitions

```python
class Partition(BaseModel):
    name: str
    size_bytes: int
    type: str             # "83" = Linux, "82" = Swap, "8e" = LVM, etc.
    filesystem: str       # "ext4", "xfs", "btrfs", etc.
    mountpoint: str
    used_bytes: int
    free_bytes: int
```

---

## ZFS Management

When `zpool` is available (`shutil.which("zpool")`):

```python
class ZFSPool(BaseModel):
    name: str
    status: str           # "ONLINE", "DEGRADED", "FAULTED"
    size_bytes: int
    alloc_bytes: int
    free_bytes: int
    health: str
    datasets: List[ZFSDataset]
```

ZFS commands used:
- `zpool list -j` – Pool list with status
- `zpool status <pool>` – Detailed pool status
- `zfs list -j` – Dataset list
- `zpool create ...` – Create pool
- `zpool add ...` – Add drive to pool
- `zpool destroy <pool>` – Destroy pool

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/drives` | All physical drives |
| `GET` | `/drives/{name}` | Drive details with SMART |
| `GET` | `/drives/{name}/partitions` | Partition list |
| `POST` | `/drives/{name}/partitions` | Create partition |
| `DELETE` | `/drives/{name}/partitions/{part}` | Delete partition |
| `POST` | `/drives/{name}/partitions/{part}/format` | Format partition |
| `POST` | `/drives/{name}/partitions/{part}/mount` | Mount partition |
| `POST` | `/drives/{name}/partitions/{part}/unmount` | Unmount |
| `GET` | `/drives/mounts` | All mount points |
| `GET` | `/drives/zfs/pools` | All ZFS pools |
| `POST` | `/drives/zfs/pools` | Create ZFS pool |
| `DELETE` | `/drives/zfs/pools/{name}` | Destroy ZFS pool |
| `GET` | `/drives/zfs/pools/{name}/datasets` | Datasets of a pool |
| `POST` | `/drives/zfs/pools/{name}/datasets` | Create dataset |

---

## Safety Notes

- Formatting and deletion of partitions are **destructive operations** with no undo
- ZFS pool destruction is irreversible
- These endpoints are protected by admin or storage group privileges
- No dry-run mode — always back up data before using these endpoints
