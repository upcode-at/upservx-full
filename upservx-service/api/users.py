"""User and group management routes."""

from fastapi import APIRouter, HTTPException

from lib.models import (
    UserCreateModel, UserUpdateModel,
    GroupCreateModel, GroupUpdateModel, SSHKeyListModel,
)
from lib.logger import log_user, log_ssh
from handlers.users import (
    list_system_users, list_system_groups,
    create_user, update_user, delete_user,
    create_group, update_group, delete_group,
    read_authorized_keys, write_authorized_keys,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/users")
def api_list_users():
    """List system users."""
    return {"users": [u.dict() for u in list_system_users()]}


@router.post("/users")
def api_create_user(payload: UserCreateModel):
    """Create a system user."""
    try:
        user = create_user(payload)
        log_user(f"Created user [{payload.username}]")
        return user.dict()
    except Exception as e:
        log_user(f"Failed to create user [{payload.username}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/users/{username}")
def api_update_user(username: str, payload: UserUpdateModel):
    """Update a system user."""
    try:
        user = update_user(username, payload)
        log_user(f"Updated user [{username}]")
        return user.dict()
    except Exception as e:
        log_user(f"Failed to update user [{username}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/users/{username}")
def api_delete_user(username: str):
    """Delete a system user."""
    try:
        delete_user(username)
        log_user(f"Deleted user [{username}]")
        return {"detail": "deleted"}
    except Exception as e:
        log_user(f"Failed to delete user [{username}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/{username}/keys")
def api_get_ssh_keys(username: str):
    """Get SSH authorized keys for a user."""
    keys = read_authorized_keys(username)
    return {"keys": keys}


@router.put("/users/{username}/keys")
def api_set_ssh_keys(username: str, payload: SSHKeyListModel):
    """Set SSH authorized keys for a user."""
    try:
        write_authorized_keys(username, payload.keys)
        log_ssh(f"Updated SSH keys for [{username}]")
        return {"detail": "updated"}
    except Exception as e:
        log_ssh(f"Failed to update SSH keys for [{username}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------

@router.get("/groups")
def api_list_groups():
    """List system groups."""
    return {"groups": [g.dict() for g in list_system_groups()]}


@router.post("/groups")
def api_create_group(payload: GroupCreateModel):
    """Create a system group."""
    try:
        group = create_group(payload)
        log_user(f"Created group [{payload.name}]")
        return group.dict()
    except Exception as e:
        log_user(f"Failed to create group [{payload.name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/groups/{name}")
def api_update_group(name: str, payload: GroupUpdateModel):
    """Update a system group."""
    try:
        group = update_group(name, payload)
        log_user(f"Updated group [{name}]")
        return group.dict()
    except Exception as e:
        log_user(f"Failed to update group [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/groups/{name}")
def api_delete_group(name: str):
    """Delete a system group."""
    try:
        delete_group(name)
        log_user(f"Deleted group [{name}]")
        return {"detail": "deleted"}
    except Exception as e:
        log_user(f"Failed to delete group [{name}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))
