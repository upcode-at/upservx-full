# Data Models

**File:** `upservx-service/models.py` (440 lines)

---

## Overview

The `models.py` file defines all **Pydantic v2 models** for request validation and response serialization in the Upcode Harbor backend.

---

## Auth Models

```python
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    token: str
    username: str
    permissions: PermissionSummary

class PermissionSummary(BaseModel):
    is_admin: bool
    has_container_access: bool
    has_vm_access: bool
    has_storage_access: bool
    has_shell_access: bool
    has_log_access: bool
    groups: List[str]
```

---

## Container Models

```python
class ContainerCreateRequest(BaseModel):
    name: str
    image: str
    type: str = "docker"           # "docker" or "lxc"
    ports: List[PortMapping] = []
    volumes: List[VolumeMount] = []
    env: List[EnvVar] = []
    restart_policy: str = "unless-stopped"
    network: str = "bridge"
    memory_mb: int = 0             # 0 = unlimited
    cpu_limit: float = 0.0         # 0 = unlimited
    command: str = ""

class PortMapping(BaseModel):
    host_port: int
    container_port: int
    protocol: str = "tcp"

class VolumeMount(BaseModel):
    host_path: str
    container_path: str
    read_only: bool = False

class EnvVar(BaseModel):
    name: str
    value: str
```

---

## VM Models

```python
class VMCreateRequest(BaseModel):
    name: str
    memory_mb: int = 1024
    vcpus: int = 1
    disk_gb: int = 20
    iso: str = ""
    network: str = "default"
    os_variant: str = "generic"

class VMResponse(BaseModel):
    name: str
    uuid: str
    status: str
    vcpus: int
    memory_mb: int
    disks: List[str]
    vnc_port: int
```

---

## Storage Models

```python
class DriveResponse(BaseModel):
    name: str
    model: str
    size_bytes: int
    type: str
    partitions: List[PartitionResponse]
    smart_status: str
    temperature: Optional[int]

class PartitionCreateRequest(BaseModel):
    size_mb: int          # 0 = use remaining space
    type: str = "primary"
    filesystem: str = "ext4"

class MountRequest(BaseModel):
    mountpoint: str
    options: str = "defaults"
```

---

## Backup Models

```python
class BackupJobRequest(BaseModel):
    name: str
    type: str             # "docker_volume", "docker_container", "vm", "directory"
    source: str
    destination: str
    schedule: str         # Cron expression
    retention_count: int = 7
    enabled: bool = True

class BackupResultResponse(BaseModel):
    id: int
    job_id: int
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    size_bytes: int
    path: str
    error_message: Optional[str]
```

---

## Settings Models

```python
class SettingsUpdateRequest(BaseModel):
    instance_name: Optional[str]
    theme: Optional[str]
    metrics_interval_seconds: Optional[int]
    alert_cpu_percent: Optional[int]
    alert_memory_percent: Optional[int]
    alert_disk_percent: Optional[int]
    auto_update_check: Optional[bool]

class APIKeyResponse(BaseModel):
    key: str              # Only shown once!
    created_at: datetime
```

---

## Cluster Models

```python
class ClusterRegisterRequest(BaseModel):
    master_url: str
    token: str
    node_name: str
    node_url: str

class NodeResponse(BaseModel):
    id: str
    name: str
    url: str
    status: str
    last_seen: datetime
    version: str
    metrics: Optional[dict]

class ClusterStatusResponse(BaseModel):
    role: str             # "master", "child", "standalone"
    nodes: List[NodeResponse]
    cluster_name: str
```

---

## Error Models

```python
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str]
    code: Optional[str]

class SuccessResponse(BaseModel):
    success: bool
    message: Optional[str]
```

---

## Pydantic v2 Configuration

All models use Pydantic v2 syntax:

```python
from pydantic import BaseModel, Field, field_validator

class ExampleModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",          # Reject unknown fields
        str_strip_whitespace=True
    )

    name: str = Field(..., min_length=1, max_length=64)
    count: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError("Invalid name")
        return v
```
