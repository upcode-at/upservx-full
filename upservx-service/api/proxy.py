"""Reverse proxy management routes."""

from fastapi import APIRouter, HTTPException

from lib.models import ProxyConfigCreate, CertificateRequest
from lib.logger import log_proxy
from handlers.reverse_proxy import reverse_proxy_manager

router = APIRouter()


@router.get("/proxy/status")
def api_proxy_status():
    """Get reverse proxy status."""
    try:
        return reverse_proxy_manager.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proxy/configs")
def api_list_proxy_configs():
    """List all proxy configurations."""
    return {"configs": reverse_proxy_manager.list_configs()}


@router.post("/proxy/configs")
def api_create_proxy_config(payload: ProxyConfigCreate):
    """Create a new proxy configuration."""
    try:
        result = reverse_proxy_manager.create_config(payload)
        log_proxy(f"Created proxy config for [{payload.domain}]")
        return result
    except Exception as e:
        log_proxy(f"Failed to create proxy config for [{payload.domain}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/proxy/configs/{domain}")
def api_delete_proxy_config(domain: str):
    """Delete a proxy configuration."""
    try:
        reverse_proxy_manager.delete_config(domain)
        log_proxy(f"Deleted proxy config for [{domain}]")
        return {"detail": "deleted"}
    except Exception as e:
        log_proxy(f"Failed to delete proxy config for [{domain}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/proxy/certificates")
def api_list_certificates():
    """List SSL certificates managed by the proxy."""
    return {"certificates": reverse_proxy_manager.list_certificates()}


@router.post("/proxy/certificates/obtain")
def api_obtain_certificate(payload: CertificateRequest):
    """Obtain a new SSL certificate via Let's Encrypt."""
    try:
        result = reverse_proxy_manager.obtain_certificate(payload.domain, payload.email)
        log_proxy(f"Obtained SSL certificate for [{payload.domain}]")
        return result
    except Exception as e:
        log_proxy(f"Failed to obtain certificate for [{payload.domain}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/proxy/certificates/renew")
def api_renew_certificate(payload: CertificateRequest):
    """Renew an existing SSL certificate."""
    try:
        result = reverse_proxy_manager.renew_certificate(payload.domain)
        log_proxy(f"Renewed SSL certificate for [{payload.domain}]")
        return result
    except Exception as e:
        log_proxy(f"Failed to renew certificate for [{payload.domain}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/proxy/certificates/{domain}")
def api_delete_certificate(domain: str):
    """Delete an SSL certificate."""
    try:
        reverse_proxy_manager.delete_certificate(domain)
        log_proxy(f"Deleted SSL certificate for [{domain}]")
        return {"detail": "deleted"}
    except Exception as e:
        log_proxy(f"Failed to delete certificate for [{domain}]: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))
