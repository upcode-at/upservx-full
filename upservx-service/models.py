"""
Pydantic models for the UpservX API.
"""

from pydantic import BaseModel
from typing import List, Optional

class Container(BaseModel):
    id: int
    name: str
    type: str
    status: str
    image: str
    ports: List[str] = []
    mounts: List[str] = []
    envs: List[str] = []
    cpu: float
    memory: int
    created: str

class ContainerCreate(BaseModel):
    name: str
    type: str
    image: str
    ports: List[str] = []
    mounts: List[str] = []
    envs: List[str] = []
    cpu: float = 0.0
    memory: int = 0

class ISOInfo(BaseModel):
    id: int
    name: str
    size: float
    type: str
    version: str
    architecture: str
    created: str
    used: bool
    path: str

class ISODownloadRequest(BaseModel):
    url: str
    name: str | None = None

class ContainerImageInfo(BaseModel):
    id: int
    repository: str
    tag: str
    imageId: str
    size: float
    created: str
    used: bool = False
    pulls: int = 0

class ImagePullRequest(BaseModel):
    image: str
    registry: str | None = None
    type: str = "docker"

class LogInfo(BaseModel):
    name: str
    size: int

class DriveInfo(BaseModel):
    device: str
    name: str
    type: str
    size: float
    used: float
    available: float
    filesystem: str
    mountpoint: str
    mounted: bool
    temperature: int | None = None

class DriveMountRequest(BaseModel):
    device: str
    mountpoint: str

class DriveUnmountRequest(BaseModel):
    device: str | None = None
    mountpoint: str | None = None

class DriveFormatRequest(BaseModel):
    device: str
    filesystem: str
    label: str | None = None

class ZFSDeviceInfo(BaseModel):
    path: str
    status: str

class ZFSPoolInfo(BaseModel):
    name: str
    type: str
    size: float
    used: float
    available: float
    mountpoint: str
    devices: List[ZFSDeviceInfo]

class ZFSPoolCreateRequest(BaseModel):
    name: str
    devices: List[str]
    raid: str = "stripe"

class NetworkInterfaceInfo(BaseModel):
    name: str
    type: str
    status: str
    ip: str
    netmask: str
    gateway: str
    mac: str
    speed: str
    rx: str
    tx: str

class NetworkSettingsModel(BaseModel):
    dns_primary: str = "8.8.8.8"
    dns_secondary: str = "8.8.4.4"

class SettingsModel(BaseModel):
    hostname: str
    timezone: str
    auto_updates: bool
    monitoring: bool
    ssh_port: int = 22
    api_key: Optional[str] = None

class InterfaceConfigModel(BaseModel):
    """Model for configuring a network interface.

    - method: 'dhcp' or 'static'
    - ip/netmask/gateway: used when method == 'static'
    - enabled: whether the interface should be up
    """
    method: str = "dhcp"
    ip: Optional[str] = None
    netmask: Optional[str] = None
    gateway: Optional[str] = None
    enabled: bool = True

class SystemUserModel(BaseModel):
    username: str
    uid: int
    gid: int
    groups: List[str]
    shell: str
    home: str
    description: str | None = ""

class SystemGroupModel(BaseModel):
    name: str
    gid: int
    members: List[str]
    description: str | None = ""

class UserCreateModel(BaseModel):
    username: str
    password: str
    groups: List[str] = []
    shell: str = "/bin/bash"

class UserUpdateModel(BaseModel):
    groups: List[str] | None = None
    shell: str | None = None

class GroupCreateModel(BaseModel):
    name: str
    members: List[str] = []

class GroupUpdateModel(BaseModel):
    members: List[str] | None = None

class SSHKeyListModel(BaseModel):
    keys: List[str] = []

class VirtualMachine(BaseModel):
    id: int
    name: str
    status: str
    cpu: int
    memory: int
    iso: str
    disks: List[str]
    created: str
    autostart: bool | None = None
    network_bridge: str | None = None
    graphics: str | None = None
    cloud_init_iso: str | None = None
    storage_path: str | None = None
    cpu_usage: float | None = None  # CPU usage percentage
    memory_usage: float | None = None  # Memory usage percentage

class DiskConfig(BaseModel):
    size: int
    format: str = "qcow2"  # qcow2, raw, vmdk

class VirtualMachineCreate(BaseModel):
    name: str
    cpu: int
    memory: int
    iso: str
    disks: List[DiskConfig] = []
    network_mode: str = "nat"  # "nat", "bridge", "none", "unconfigured"
    bridge_interface: str | None = None  # physical interface for bridge mode
    autostart: bool = False
    cloud_init: str | None = None
    storage_path: str | None = None  # path to mounted drive for VM disks (e.g., /mnt/ssd1)

class VirtualMachineUpdate(BaseModel):
    cpu: Optional[int] = None
    memory: Optional[int] = None
    iso: Optional[str] = None
    add_disks: List[DiskConfig] = []
    autostart: Optional[bool] = None
    network_mode: Optional[str] = None
    bridge_interface: Optional[str] = None
    remove_disks: List[str] = []
    storage_path: Optional[str] = None  # path to mounted drive for new VM disks

class BackupServer(BaseModel):
    id: int
    name: str
    type: str  # 'local', 'remote'
    status: str  # 'connected', 'disconnected', 'error'
    host: Optional[str] = None  # For remote servers
    port: Optional[int] = None  # For remote servers
    remote_path: Optional[str] = None  # For remote servers
    local_path: Optional[str] = None  # For local storage
    auth_type: Optional[str] = None  # 'password', 'ssh_key'
    username: Optional[str] = None  # For remote servers
    capacity_gb: Optional[float] = None
    used_gb: Optional[float] = None
    last_sync: Optional[str] = None
    created: str

class BackupServerCreate(BaseModel):
    name: str
    type: str  # 'local', 'remote'
    host: Optional[str] = None
    port: Optional[int] = 22
    remote_path: Optional[str] = '/backups'
    local_path: Optional[str] = '/var/backups'
    auth_type: Optional[str] = None  # 'password', 'ssh_key'
    username: Optional[str] = None
    password: Optional[str] = None  # Will be encrypted
    ssh_key: Optional[str] = None  # SSH private key content
    ssh_key_passphrase: Optional[str] = None

class BackupServerUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    remote_path: Optional[str] = None
    local_path: Optional[str] = None
    auth_type: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssh_key: Optional[str] = None
    ssh_key_passphrase: Optional[str] = None

class BackupJob(BaseModel):
    id: int
    name: str
    backup_type: str  # 'vm', 'container', 'system', 'database'
    targets: List[str]  # List of target names/paths
    schedule: str  # Cron-like schedule
    server_id: int  # Reference to BackupServer
    status: str  # 'active', 'paused', 'error'
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    last_size: Optional[int] = None  # Size in bytes
    retention_days: int = 30
    compression: bool = True
    created: str

class BackupJobCreate(BaseModel):
    name: str
    backup_type: str
    targets: List[str]
    schedule: str
    server_id: int
    retention_days: int = 30
    compression: bool = True

class BackupJobUpdate(BaseModel):
    name: Optional[str] = None
    backup_type: Optional[str] = None
    targets: Optional[List[str]] = None
    schedule: Optional[str] = None
    server_id: Optional[int] = None
    status: Optional[str] = None
    retention_days: Optional[int] = None
    compression: Optional[bool] = None

class BackupInstance(BaseModel):
    id: int
    job_id: int
    server_id: int
    backup_name: str
    backup_path: str
    backup_size: int  # Size in bytes
    status: str  # 'completed', 'failed', 'in_progress'
    created: str
    backup_type: str
    targets: List[str]

class BackupExecuteRequest(BaseModel):
    job_id: int

class BackupRestoreRequest(BaseModel):
    backup_id: int
    restore_path: str

class BackupListResponse(BaseModel):
    backups: List[BackupInstance]
    total: int

class BackupServerInfo(BaseModel):
    server_id: int
    name: str
    type: str
    status: str
    storage_info: dict

class ProxyConfigModel(BaseModel):
    domain: str
    backend_host: str = "127.0.0.1"
    backend_port: int = 9500
    frontend_port: int = 9200
    ssl_enabled: bool = False
    force_ssl: bool = False

class ProxyConfigCreate(BaseModel):
    domain: str
    backend_host: str = "127.0.0.1"
    backend_port: int = 9500
    frontend_port: int = 9200
    ssl_enabled: bool = False
    force_ssl: bool = False

class CertificateRequest(BaseModel):
    domain: str
    email: str

class CertificateInfo(BaseModel):
    name: str
    domains: str
    expiry: str
    cert_path: Optional[str] = None

class FirewallRuleCreate(BaseModel):
    chain: str  # input, output, forward
    protocol: Optional[str] = None  # tcp, udp, icmp, all
    port: Optional[int] = None
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    action: str = "accept"  # accept, drop, reject
    comment: Optional[str] = None
    position: Optional[int] = None

class FirewallRuleDelete(BaseModel):
    chain: str
    handle: int

class FirewallChainPolicy(BaseModel):
    chain: str
    policy: str  # accept, drop

class PortForwardCreate(BaseModel):
    external_port: int
    internal_ip: str
    internal_port: int
    protocol: str = "tcp"
    comment: Optional[str] = None

class MasqueradeCreate(BaseModel):
    interface: str

class DockerVolumeInfo(BaseModel):
    name: str
    driver: str
    mountpoint: str
    size: Optional[float] = None
    used: Optional[float] = None
    created: Optional[str] = None

class LXCStorageInfo(BaseModel):
    name: str
    type: str
    source: str
    size: Optional[float] = None
    used: Optional[float] = None
    available: Optional[float] = None
    description: Optional[str] = None

class DockerVolumeCreate(BaseModel):
    name: str

class LXCStorageCreate(BaseModel):
    name: str
    driver: str = "dir"
    source: str = ""