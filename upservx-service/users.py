import os
import pwd
import grp
from typing import List

from pydantic import BaseModel


LOGIN_SHELLS = {
    "/bin/bash",
    "/bin/sh",
    "/bin/fish",
    "/bin/zsh",
    "/usr/bin/bash",
    "/usr/bin/sh",
    "/usr/bin/fish",
    "/usr/bin/zsh",
}


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


def list_system_users() -> List[SystemUserModel]:
    users: List[SystemUserModel] = []
    all_groups = grp.getgrall()
    for entry in pwd.getpwall():
        if entry.pw_shell not in LOGIN_SHELLS:
            continue
        groups = [g.gr_name for g in all_groups if entry.pw_name in g.gr_mem or g.gr_gid == entry.pw_gid]
        users.append(
            SystemUserModel(
                username=entry.pw_name,
                uid=entry.pw_uid,
                gid=entry.pw_gid,
                groups=groups,
                shell=entry.pw_shell,
                home=entry.pw_dir,
                description=entry.pw_gecos.split(',')[0] if entry.pw_gecos else "",
            )
        )
    return users


def list_system_groups() -> List[SystemGroupModel]:
    groups: List[SystemGroupModel] = []
    for entry in grp.getgrall():
        groups.append(
            SystemGroupModel(
                name=entry.gr_name,
                gid=entry.gr_gid,
                members=list(entry.gr_mem),
            )
        )
    return groups


def _authorized_keys_path(username: str) -> str:
    info = pwd.getpwnam(username)
    return os.path.join(info.pw_dir, ".ssh", "authorized_keys")


def read_authorized_keys(username: str) -> List[str]:
    path = _authorized_keys_path(username)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return [line.strip() for line in f if line.strip()]
        except Exception:
            return []
    return []


def write_authorized_keys(username: str, keys: List[str]) -> None:
    info = pwd.getpwnam(username)
    ssh_dir = os.path.join(info.pw_dir, ".ssh")
    os.makedirs(ssh_dir, exist_ok=True)
    path = os.path.join(ssh_dir, "authorized_keys")
    with open(path, "w") as f:
        for key in keys:
            f.write(key.strip() + "\n")
    os.chown(ssh_dir, info.pw_uid, info.pw_gid)
    os.chmod(ssh_dir, 0o700)
    os.chown(path, info.pw_uid, info.pw_gid)
    os.chmod(path, 0o600)

