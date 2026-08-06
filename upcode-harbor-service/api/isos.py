"""ISO management routes."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from lib.models import ISODownloadRequest
from lib.logger import log_iso
from handlers.isos import get_iso_files, download_iso, save_uploaded_iso, delete_iso, get_iso_path

router = APIRouter()


@router.get("/isos")
def list_isos():
    """List available ISO files."""
    return {"isos": [iso.dict() for iso in get_iso_files()]}


@router.post("/isos/download")
def download_iso_endpoint(payload: ISODownloadRequest):
    """Download an ISO file from a URL."""
    try:
        info = download_iso(payload.url, payload.name)
        log_iso(f"Downloaded ISO [{info.name}] from {payload.url}")
        return info.dict()
    except Exception as e:
        log_iso(f"Failed to download ISO from {payload.url}: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/isos")
async def upload_iso(file: UploadFile = File(...)):
    """Upload a new ISO file."""
    filename = file.filename or "upload.iso"
    content = await file.read()
    try:
        info = save_uploaded_iso(content, filename)
        log_iso(f"Uploaded ISO [{info.name}]")
        return info.dict()
    except Exception as e:
        log_iso(f"Failed to upload ISO [{filename}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/debug/echo")
async def debug_echo():
    """Disabled in production – returns 404."""
    raise HTTPException(status_code=404, detail="Not found")


@router.delete("/isos/{name}")
def delete_iso_endpoint(name: str):
    """Delete an ISO file."""
    try:
        delete_iso(name)
        log_iso(f"Deleted ISO [{name}]")
        return {"detail": "deleted"}
    except Exception as e:
        log_iso(f"Failed to delete ISO [{name}]: {e}", error=True)
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/isos/{name}/file")
def download_iso_file(name: str):
    """Download an ISO file."""
    try:
        path = get_iso_path(name)
        return FileResponse(path, filename=name, media_type="application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
