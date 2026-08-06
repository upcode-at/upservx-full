"""Generated from the FastAPI OpenAPI schema. Do not edit by hand."""

from typing import Any, Literal, NotRequired, TypedDict

class BackupServerCreate(TypedDict):
    name: str
    type: Literal['local', 'remote']
    host: NotRequired[str | None]
    port: NotRequired[int | None]
    remote_path: NotRequired[str | None]
    local_path: NotRequired[str | None]
    auth_type: NotRequired[Literal['password', 'ssh_key'] | None]
    username: NotRequired[str | None]
    password: NotRequired[str | None]
    ssh_key: NotRequired[str | None]
    ssh_key_passphrase: NotRequired[str | None]

class BackupServerUpdate(TypedDict):
    name: NotRequired[str | None]
    type: NotRequired[Literal['local', 'remote'] | None]
    host: NotRequired[str | None]
    port: NotRequired[int | None]
    remote_path: NotRequired[str | None]
    local_path: NotRequired[str | None]
    auth_type: NotRequired[Literal['password', 'ssh_key'] | None]
    username: NotRequired[str | None]
    password: NotRequired[str | None]
    ssh_key: NotRequired[str | None]
    ssh_key_passphrase: NotRequired[str | None]

class BackupJobCreate(TypedDict):
    name: str
    backup_type: Literal['vm', 'container', 'system', 'database']
    targets: list[str]
    schedule: str
    server_id: int
    retention_days: NotRequired[int]
    compression: NotRequired[bool]

class BackupJobUpdate(TypedDict):
    name: NotRequired[str | None]
    backup_type: NotRequired[Literal['vm', 'container', 'system', 'database'] | None]
    targets: NotRequired[list[str] | None]
    schedule: NotRequired[str | None]
    server_id: NotRequired[int | None]
    status: NotRequired[Literal['active', 'paused', 'error'] | None]
    retention_days: NotRequired[int | None]
    compression: NotRequired[bool | None]

class BackupRestoreRequest(TypedDict):
    restore_path: str

class SSHKeyGenerateRequest(TypedDict):
    key_name: str
    key_type: NotRequired[str]
    key_size: NotRequired[int]
    passphrase: NotRequired[str | None]

class SSHKeyImportRequest(TypedDict):
    key_name: str
    private_key: str
    passphrase: NotRequired[str | None]

class SSHKeyTestRequest(TypedDict):
    host: str
    username: str
    port: NotRequired[int]
    passphrase: NotRequired[str | None]

class AppInstallRequest(TypedDict):
    custom_name: NotRequired[str | None]
    environment: NotRequired[dict[str, str]]
