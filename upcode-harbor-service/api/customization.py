"""
API routes for application customization (logo, login banner).
Stored in /opt/upcode-harbor/customization/
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import json
from lib.secure_store import ensure_config_directory, secure_write_bytes, secure_write_json

router = APIRouter(prefix="/settings/customization", tags=["customization"])

CUSTOMIZATION_DIR = "/etc/upcode-harbor/customization"
CONFIG_FILE = os.path.join(CUSTOMIZATION_DIR, "config.json")

SUPPORTED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}

DEFAULT_CONFIG = {
    "banner_title": "Welcome to Upcode Harbor",
    "banner_subtitle": "Professional Server Management Platform",
    "logo_file": None,
    "banner_file": None,
}


def _ensure_dir():
    ensure_config_directory(CUSTOMIZATION_DIR)


def _read_config() -> dict:
    _ensure_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def _write_config(config: dict):
    _ensure_dir()
    secure_write_json(CONFIG_FILE, config)


def _find_file(prefix: str) -> Optional[str]:
    """Find an existing logo or banner file by prefix (e.g. 'logo', 'banner')."""
    if not os.path.isdir(CUSTOMIZATION_DIR):
        return None
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]:
        candidate = os.path.join(CUSTOMIZATION_DIR, f"{prefix}{ext}")
        if os.path.exists(candidate):
            return candidate
    return None


class CustomizationConfig(BaseModel):
    banner_title: Optional[str] = None
    banner_subtitle: Optional[str] = None


@router.get("")
def get_customization():
    """Return current customization config. Public – no auth required."""
    config = _read_config()

    logo_path = _find_file("logo")
    banner_path = _find_file("banner")

    return {
        "banner_title": config.get("banner_title", DEFAULT_CONFIG["banner_title"]),
        "banner_subtitle": config.get("banner_subtitle", DEFAULT_CONFIG["banner_subtitle"]),
        "has_logo": logo_path is not None,
        "has_banner": banner_path is not None,
    }


@router.post("")
def save_customization(body: CustomizationConfig):
    """Save banner title and subtitle. Requires admin."""
    config = _read_config()
    if body.banner_title is not None:
        config["banner_title"] = body.banner_title
    if body.banner_subtitle is not None:
        config["banner_subtitle"] = body.banner_subtitle
    _write_config(config)
    return {"detail": "Customization saved"}


@router.post("/logo")
async def upload_logo(file: UploadFile = File(...)):
    """Upload a custom logo image. Saved as /opt/upcode-harbor/customization/logo.<ext>."""
    _ensure_dir()

    content_type = file.content_type or ""
    ext = SUPPORTED_IMAGE_TYPES.get(content_type)
    if not ext:
        # fallback: try to derive from filename
        orig = file.filename or ""
        for e in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]:
            if orig.lower().endswith(e):
                ext = e
                break
        if not ext:
            raise HTTPException(status_code=400, detail="Unsupported image type")

    # Remove old logo files with any extension
    for old_ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]:
        old = os.path.join(CUSTOMIZATION_DIR, f"logo{old_ext}")
        if os.path.exists(old):
            os.remove(old)

    dest = os.path.join(CUSTOMIZATION_DIR, f"logo{ext}")
    secure_write_bytes(dest, await file.read())

    return {"detail": "Logo uploaded", "filename": f"logo{ext}"}


@router.delete("/logo")
def delete_logo():
    """Remove the custom logo and revert to default."""
    removed = False
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]:
        p = os.path.join(CUSTOMIZATION_DIR, f"logo{ext}")
        if os.path.exists(p):
            os.remove(p)
            removed = True
    if not removed:
        raise HTTPException(status_code=404, detail="No custom logo found")
    return {"detail": "Logo removed"}


@router.post("/banner")
async def upload_banner(file: UploadFile = File(...)):
    """Upload a custom login banner image. Saved as /opt/upcode-harbor/customization/banner.<ext>."""
    _ensure_dir()

    content_type = file.content_type or ""
    ext = SUPPORTED_IMAGE_TYPES.get(content_type)
    if not ext:
        orig = file.filename or ""
        for e in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]:
            if orig.lower().endswith(e):
                ext = e
                break
        if not ext:
            raise HTTPException(status_code=400, detail="Unsupported image type")

    for old_ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]:
        old = os.path.join(CUSTOMIZATION_DIR, f"banner{old_ext}")
        if os.path.exists(old):
            os.remove(old)

    dest = os.path.join(CUSTOMIZATION_DIR, f"banner{ext}")
    secure_write_bytes(dest, await file.read())

    return {"detail": "Banner uploaded", "filename": f"banner{ext}"}


@router.delete("/banner")
def delete_banner():
    """Remove the custom banner image and revert to default."""
    removed = False
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"]:
        p = os.path.join(CUSTOMIZATION_DIR, f"banner{ext}")
        if os.path.exists(p):
            os.remove(p)
            removed = True
    if not removed:
        raise HTTPException(status_code=404, detail="No custom banner found")
    return {"detail": "Banner removed"}


@router.get("/logo/file")
def serve_logo():
    """Serve the custom logo file."""
    path = _find_file("logo")
    if not path:
        raise HTTPException(status_code=404, detail="No custom logo uploaded")
    return FileResponse(path)


@router.get("/banner/file")
def serve_banner():
    """Serve the custom banner image file."""
    path = _find_file("banner")
    if not path:
        raise HTTPException(status_code=404, detail="No custom banner uploaded")
    return FileResponse(path)
