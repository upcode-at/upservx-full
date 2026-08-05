"""
Security API endpoints

Covers:
- Fail2Ban jail & ban management
- Upgradeable / security package scanning
- SSL/TLS certificate inspection
- Open port / network exposure scanning
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any
from lib.jobs import enqueue_job

from handlers.security import (
    get_all_fail2ban_jails,
    unban_ip,
    get_certificates,
    get_open_ports,
)

router = APIRouter(prefix="/security", tags=["security"])


# ---------------------------------------------------------------------------
# Fail2Ban
# ---------------------------------------------------------------------------

@router.get("/fail2ban")
async def list_fail2ban_jails() -> Dict[str, Any]:
    """Return all Fail2Ban jails with current ban counts and banned IPs."""
    try:
        return get_all_fail2ban_jails()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class UnbanRequest(BaseModel):
    jail: str
    ip: str


@router.post("/fail2ban/unban")
async def unban_fail2ban_ip(body: UnbanRequest) -> Dict[str, Any]:
    """Unban an IP address from a Fail2Ban jail."""
    try:
        result = unban_ip(body.jail, body.ip)
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Package / CVE updates
# ---------------------------------------------------------------------------

@router.get("/packages", status_code=202)
async def list_upgradeable_packages() -> Dict[str, Any]:
    """Queue the package metadata refresh and upgrade scan."""
    job = enqueue_job(
        "package_scan",
        {},
        idempotency_key="package-scan",
        resource_type="security_scan",
        resource_id="packages",
    )
    return {"message": "Package scan queued", "persistent_job": job}


@router.post("/packages/upgrade", status_code=202)
async def upgrade_all_packages() -> Dict[str, Any]:
    """Queue a full package upgrade."""
    job = enqueue_job(
        "package_upgrade",
        {},
        idempotency_key="package-upgrade:all",
        resource_type="package_upgrade",
        resource_id="all",
    )
    return {"message": "Package upgrade queued", "persistent_job": job}


@router.post("/packages/upgrade/{name}", status_code=202)
async def upgrade_single_package(name: str) -> Dict[str, Any]:
    """Queue one package upgrade."""
    job = enqueue_job(
        "package_upgrade",
        {"package_name": name},
        idempotency_key=f"package-upgrade:{name}",
        resource_type="package_upgrade",
        resource_id=name,
    )
    return {"message": "Package upgrade queued", "persistent_job": job}


# ---------------------------------------------------------------------------
# SSL / TLS certificates
# ---------------------------------------------------------------------------

@router.get("/certificates")
async def list_certificates() -> Dict[str, Any]:
    """Scan common certificate directories and return expiry information."""
    try:
        return get_certificates()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Open ports
# ---------------------------------------------------------------------------

@router.get("/ports")
async def list_open_ports() -> Dict[str, Any]:
    """Return all listening TCP/UDP ports with process information."""
    try:
        return get_open_ports()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# CVE Scanner
# ---------------------------------------------------------------------------

@router.get("/cve", status_code=202)
async def scan_cve_vulnerabilities(
    limit: int = Query(default=300, ge=50, le=1000, description="Max packages to scan")
) -> Dict[str, Any]:
    """Queue an installed-package CVE scan."""
    job = enqueue_job(
        "cve_scan",
        {"limit": limit},
        idempotency_key=f"cve-scan:{limit}",
        resource_type="security_scan",
        resource_id="host",
    )
    return {"message": "CVE scan queued", "persistent_job": job}


@router.get("/container-cve", status_code=202)
async def scan_container_cve_vulnerabilities(
    container_limit: int = Query(default=30, ge=1, le=100, description="Max Docker/LXC containers to scan"),
    package_limit: int = Query(default=200, ge=20, le=1000, description="Max packages per container"),
) -> Dict[str, Any]:
    """Queue a Docker/LXC CVE scan."""
    job = enqueue_job(
        "container_cve_scan",
        {"container_limit": container_limit, "package_limit": package_limit},
        idempotency_key=f"container-cve:{container_limit}:{package_limit}",
        resource_type="security_scan",
        resource_id="containers",
    )
    return {"message": "Container CVE scan queued", "persistent_job": job}
