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


class ContainerImageInfo(BaseModel):
    id: int
    repository: str
    tag: str
    imageId: str
    size: float
    created: str
    used: bool = False
    pulls: int = 0


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


class VirtualMachine(BaseModel):
    id: int
    name: str
    status: str
    cpu: int
    memory: int
    iso: str
    disks: List[str]
    created: str


class VirtualMachineCreate(BaseModel):
    name: str
    cpu: int
    memory: int
    iso: str
    disks: List[int] = []


class VirtualMachineUpdate(BaseModel):
    cpu: Optional[int] = None
    memory: Optional[int] = None
    iso: Optional[str] = None
    add_disks: List[int] = []


class ISODownloadRequest(BaseModel):
    url: str
    name: str | None = None


class ImagePullRequest(BaseModel):
    image: str
    registry: str | None = None
    type: str = "docker"


class DriveMountRequest(BaseModel):
    device: str
    mountpoint: str


class DriveFormatRequest(BaseModel):
    device: str
    filesystem: str
    label: str | None = None


class ZFSPoolCreateRequest(BaseModel):
    name: str
    devices: List[str]
    raid: str = "stripe"

