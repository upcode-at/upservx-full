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

from handlers.security import (
    get_all_fail2ban_jails,
    unban_ip,
    get_upgradeable_packages,
    get_certificates,
    get_open_ports,
    scan_cves,
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

@router.get("/packages")
async def list_upgradeable_packages() -> Dict[str, Any]:
    """Return upgradeable packages – security updates are flagged separately."""
    try:
        return get_upgradeable_packages()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

@router.get("/cve")
async def scan_cve_vulnerabilities(
    limit: int = Query(default=300, ge=50, le=1000, description="Max packages to scan")
) -> Dict[str, Any]:
    """Scan installed packages for CVEs via OSV.dev (Debian/Ubuntu only)."""
    try:
        return scan_cves(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
