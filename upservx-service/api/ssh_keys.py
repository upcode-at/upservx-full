"""Server-side SSH key management API used by backup destinations."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from handlers.ssh_keys import ssh_key_manager


router = APIRouter(prefix="/ssh-keys")


class SSHKeyGenerateRequest(BaseModel):
    key_name: str
    key_type: str = "ed25519"
    key_size: int = Field(default=4096, ge=2048, le=8192)
    passphrase: Optional[str] = None


class SSHKeyImportRequest(BaseModel):
    key_name: str
    private_key: str
    passphrase: Optional[str] = None


class SSHKeyTestRequest(BaseModel):
    host: str
    username: str
    port: int = Field(default=22, ge=1, le=65535)
    passphrase: Optional[str] = None


def _public_key_info(info: dict) -> dict:
    """Never return private key material or local private-key paths."""
    return {
        key: value
        for key, value in info.items()
        if key not in {"private_key", "private_key_path"}
    }


@router.get("")
def list_ssh_keys():
    return [_public_key_info(item) for item in ssh_key_manager.list_ssh_keys()]


@router.post("/generate")
def generate_ssh_key(request: SSHKeyGenerateRequest):
    try:
        return _public_key_info(
            ssh_key_manager.generate_ssh_key_pair(
                request.key_name,
                request.key_type,
                request.key_size,
                request.passphrase,
            )
        )
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/import")
def import_ssh_key(request: SSHKeyImportRequest):
    try:
        return _public_key_info(
            ssh_key_manager.store_ssh_key(
                request.key_name,
                request.private_key,
                request.passphrase,
            )
        )
    except FileExistsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{key_name}")
def get_ssh_key(key_name: str):
    info = ssh_key_manager.get_ssh_key(key_name)
    if not info:
        raise HTTPException(status_code=404, detail="SSH key not found")
    return _public_key_info(info)


@router.delete("/{key_name}")
def delete_ssh_key(key_name: str):
    if not ssh_key_manager.delete_ssh_key(key_name):
        raise HTTPException(status_code=404, detail="SSH key not found")
    return {"message": "SSH key deleted"}


@router.post("/{key_name}/test")
def test_ssh_key(key_name: str, request: SSHKeyTestRequest):
    info = ssh_key_manager.get_ssh_key(key_name)
    if not info:
        raise HTTPException(status_code=404, detail="SSH key not found")
    success, message = ssh_key_manager.test_ssh_connection(
        request.host,
        request.username,
        info["private_key_path"],
        request.port,
        request.passphrase,
    )
    return {"success": success, "message": message}
