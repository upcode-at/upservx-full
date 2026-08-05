"""System settings, VPN and notification management routes."""

import os
from typing import Literal

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from lib.models import SettingsModel, NotificationConfig
from lib.logger import log_vpn
from handlers.settings import (
    load_settings, save_settings, apply_system_settings,
    save_vpn_ovpn, start_vpn, stop_vpn, get_vpn_status,
)
from lib.api_tokens import create_api_token, list_api_tokens, revoke_api_token
from lib.jobs import enqueue_job
from handlers.notifications import (
    load_notifications, save_notifications, test_email, test_webhook,
)

router = APIRouter()


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    role: Literal["admin", "operator", "read-only"] = "admin"
    scopes: list[str] = Field(default_factory=lambda: ["*"])
    expires_in: int | None = Field(default=None, ge=300, le=31_536_000)


# ---------------------------------------------------------------------------
# General settings
# ---------------------------------------------------------------------------

@router.get("/settings")
def get_settings():
    """Get system settings."""
    return load_settings().dict()


@router.post("/settings")
def update_settings(payload: SettingsModel):
    """Update system settings."""
    save_settings(payload)
    apply_system_settings(payload)
    return {"detail": "saved"}


@router.post("/settings/api-key")
def generate_api_key_endpoint():
    """Compatibility endpoint that creates a revocable admin API token."""
    token, metadata = create_api_token(
        "Generated API token",
        "admin",
        ["*"],
    )
    return {"api_key": token, "token": token, **metadata}


@router.get("/settings/api-tokens")
def get_api_tokens():
    """List token metadata without returning token hashes or plaintext."""
    return {"tokens": list_api_tokens()}


@router.post("/settings/api-tokens")
def add_api_token(payload: ApiTokenCreate):
    """Create a scoped token and return its plaintext exactly once."""
    try:
        token, metadata = create_api_token(
            payload.name,
            payload.role,
            payload.scopes,
            expires_in=payload.expires_in,
        )
        return {"token": token, **metadata}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.delete("/settings/api-tokens/{token_id}")
def delete_api_token(token_id: str):
    """Revoke a token immediately."""
    if not revoke_api_token(token_id):
        raise HTTPException(status_code=404, detail="API token not found")
    return {"detail": "API token revoked", "id": token_id}


# ---------------------------------------------------------------------------
# VPN / OpenVPN
# ---------------------------------------------------------------------------

@router.post("/settings/vpn/upload")
async def upload_vpn(file: UploadFile = File(...)):
    """Upload an OpenVPN .ovpn file to the server."""
    filename = file.filename or "client.ovpn"
    content = await file.read()
    try:
        path = save_vpn_ovpn(content, filename)
        return {"detail": "saved", "path": path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/settings/vpn/file")
def download_vpn_file():
    """Download the stored .ovpn file if present."""
    try:
        status = get_vpn_status()
        ovpn_path = status.get("ovpn_path")
        if not ovpn_path:
            raise Exception("ovpn file not found")
        return FileResponse(
            ovpn_path,
            filename=os.path.basename(ovpn_path),
            media_type="application/x-openvpn-profile",
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/settings/vpn/status")
def vpn_status():
    """Get current VPN status."""
    try:
        return get_vpn_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/vpn/start")
def vpn_start():
    """Start the OpenVPN tunnel using the uploaded .ovpn file."""
    try:
        status = start_vpn()
        log_vpn("VPN tunnel started")
        return status
    except Exception as e:
        log_vpn(f"Failed to start VPN tunnel: {e}", error=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/settings/vpn/stop")
def vpn_stop():
    """Stop the OpenVPN tunnel."""
    try:
        status = stop_vpn()
        log_vpn("VPN tunnel stopped")
        return status
    except Exception as e:
        log_vpn(f"Failed to stop VPN tunnel: {e}", error=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@router.get("/settings/notifications")
def get_notification_settings():
    """Get notification configuration."""
    return load_notifications().dict()


@router.post("/settings/notifications")
def update_notification_settings(payload: NotificationConfig):
    """Save notification configuration."""
    save_notifications(payload)
    return {"detail": "saved"}


@router.post("/settings/notifications/test/email")
def test_notification_email():
    """Send a test email using the stored configuration."""
    config = load_notifications(include_secrets=True)
    result = test_email(config.email)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return {"detail": "Test email sent"}


@router.post("/settings/notifications/test/webhook")
def test_notification_webhook():
    """Send a test webhook payload using the stored configuration."""
    config = load_notifications(include_secrets=True)
    result = test_webhook(config.webhook)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return {"detail": "Test webhook sent"}


# ---------------------------------------------------------------------------
# System update
# ---------------------------------------------------------------------------

@router.post("/settings/update", status_code=202)
async def run_update():
    """Queue the system updater in the persistent job worker."""
    update_script = "/opt/upservx/update.sh"
    if not os.path.exists(update_script):
        raise HTTPException(status_code=404, detail="update.sh not found")
    job = enqueue_job(
        "system_update",
        {"script": update_script},
        idempotency_key="system-update",
        resource_type="system_update",
        resource_id="system",
    )
    return {"detail": "update queued", "persistent_job": job}
