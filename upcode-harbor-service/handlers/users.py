"""
User and group management utilities.
"""

import os
import re
import subprocess
import pwd
import grp
from typing import List
from lib.models import SystemUserModel, SystemGroupModel
from lib.logger import log_user
from lib.privileged import require_privileged

# Only allow safe POSIX usernames/groupnames
_NAME_RE = re.compile(r'^[a-zA-Z0-9_][a-zA-Z0-9_\-\.]{0,31}$')

def _validate_name(name: str, label: str = "name") -> None:
    if not _NAME_RE.match(name):
        raise ValueError(f"Invalid {label}: '{name}'. Only alphanumeric, underscore, hyphen and dot allowed.")


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
    _validate_name(username, "username")
    if shell not in LOGIN_SHELLS:
        raise ValueError(f"Invalid shell: {shell}")
    if groups:
        for g in groups:
            _validate_name(g, "group")
    cmd = ["useradd", "-m", "-s", shell]
    if groups:
        cmd.extend(["-G", ",".join(groups)])
    cmd.append(username)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to create")
    log_user(f"Created user [{username}] (shell: {shell})")
    
    if password:
        subprocess.run(["chpasswd"], input=f"{username}:{password}", text=True)


def update_user(username: str, shell: str = None, groups: List[str] = None) -> None:
    """Update an existing system user."""
    _validate_name(username, "username")
    if shell and shell not in LOGIN_SHELLS:
        raise ValueError(f"Invalid shell: {shell}")
    if groups:
        for g in groups:
            _validate_name(g, "group")
    if shell:
        result = subprocess.run(["usermod", "-s", shell, username], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "failed to update shell")
    
    if groups is not None:
        result = subprocess.run(["usermod", "-G", ",".join(groups), username], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "failed to update groups")
    log_user(f"Updated user [{username}]")


def delete_user(username: str) -> None:
    """Delete a system user."""
    _validate_name(username, "username")
    result = subprocess.run(["userdel", "-r", username], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to delete")
    log_user(f"Deleted user [{username}]")


def create_group(name: str, members: List[str] = None) -> None:
    """Create a new system group."""
    _validate_name(name, "group name")
    if members:
        for m in members:
            _validate_name(m, "member")
    result = subprocess.run(["groupadd", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to create")
    log_user(f"Created group [{name}]")
    
    if members:
        subprocess.run(["gpasswd", "-M", ",".join(members), name], capture_output=True)


def update_group(name: str, members: List[str] = None) -> None:
    """Update an existing system group."""
    _validate_name(name, "group name")
    if members:
        for m in members:
            _validate_name(m, "member")
    if members is not None:
        result = subprocess.run(["gpasswd", "-M", ",".join(members), name], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr.strip() or "failed to update members")
    log_user(f"Updated group [{name}]")


def delete_group(name: str) -> None:
    """Delete a system group."""
    _validate_name(name, "group name")
    result = subprocess.run(["groupdel", name], capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(result.stderr.strip() or "failed to delete")
    log_user(f"Deleted group [{name}]")


def _authorized_keys_path(username: str) -> str:
    """Get the path to the authorized_keys file for a user."""
    _validate_name(username, "username")
    info = pwd.getpwnam(username)
    return os.path.join(info.pw_dir, ".ssh", "authorized_keys")


def read_authorized_keys(username: str) -> List[str]:
    """Read SSH authorized keys for a user."""
    _validate_name(username, "username")
    result = require_privileged("authorized-keys-read", username)
    return [
        line.strip() for line in result.stdout.splitlines()
        if line.strip() and not line.startswith("#")
    ]


def write_authorized_keys(username: str, keys: List[str]) -> None:
    """Write SSH authorized keys for a user."""
    _validate_name(username, "username")
    content = "\n".join(key.strip() for key in keys if key.strip())
    require_privileged(
        "authorized-keys-write",
        username,
        input_text=content + ("\n" if content else ""),
    )
