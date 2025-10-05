"""
User and group management utilities.
"""

import os
import subprocess
import pwd
import grp
from typing import List
from models import SystemUserModel, SystemGroupModel


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


def list_system_users() -> List[SystemUserModel]:
    """List all system users with login shells."""
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
    """List all system groups."""
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


def create_user(username: str, password: str, groups: List[str] = None, shell: str = "/bin/bash") -> None:
    """Create a new system user."""
    cmd = ["useradd", "-m", "-s", shell]
    if groups:
        cmd.extend(["-G", ",".join(groups)])
    cmd.append(username)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to create")
    
    if password:
        subprocess.run(["chpasswd"], input=f"{username}:{password}", text=True)


def update_user(username: str, shell: str = None, groups: List[str] = None) -> None:
    """Update an existing system user."""
    if shell:
        result = subprocess.run(["usermod", "-s", shell, username], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "failed to update shell")
    
    if groups is not None:
        result = subprocess.run(["usermod", "-G", ",".join(groups), username], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "failed to update groups")


def delete_user(username: str) -> None:
    """Delete a system user."""
    result = subprocess.run(["userdel", "-r", username], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to delete")


def create_group(name: str, members: List[str] = None) -> None:
    """Create a new system group."""
    result = subprocess.run(["groupadd", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to create")
    
    if members:
        subprocess.run(["gpasswd", "-M", ",".join(members), name], capture_output=True)


def update_group(name: str, members: List[str] = None) -> None:
    """Update an existing system group."""
    if members is not None:
        result = subprocess.run(["gpasswd", "-M", ",".join(members), name], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "failed to update members")


def delete_group(name: str) -> None:
    """Delete a system group."""
    result = subprocess.run(["groupdel", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to delete")


def _authorized_keys_path(username: str) -> str:
    """Get the path to the authorized_keys file for a user."""
    info = pwd.getpwnam(username)
    return os.path.join(info.pw_dir, ".ssh", "authorized_keys")


def read_authorized_keys(username: str) -> List[str]:
    """Read SSH authorized keys for a user."""
    path = _authorized_keys_path(username)
    if os.path.exists(path):
        try:
            with open(path) as f:
                return [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except Exception:
            return []
    return []


def write_authorized_keys(username: str, keys: List[str]) -> None:
    """Write SSH authorized keys for a user."""
    info = pwd.getpwnam(username)
    ssh_dir = os.path.join(info.pw_dir, ".ssh")
    os.makedirs(ssh_dir, exist_ok=True)
    
    path = os.path.join(ssh_dir, "authorized_keys")
    with open(path, "w") as f:
        for key in keys:
            if key.strip():
                f.write(key.strip() + "\n")
    
    try:
        os.chown(ssh_dir, info.pw_uid, info.pw_gid)
        os.chmod(ssh_dir, 0o700)
        os.chown(path, info.pw_uid, info.pw_gid)
        os.chmod(path, 0o600)
    except Exception:
        pass