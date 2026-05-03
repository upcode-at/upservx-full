"""
Security Management Handler

Provides functionality for:
- Fail2Ban jail/ban management
- CVE / upgradeable package scanning
- SSL/TLS certificate inspection
- Open port / network exposure scanning
"""

import subprocess
import re
import os
import glob
import json
import shutil
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: List[str], timeout: int = 15) -> tuple[str, str, int]:
    """Run a subprocess command safely and return (stdout, stderr, returncode)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        return "", f"Command not found: {cmd[0]}", 127
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1


# ---------------------------------------------------------------------------
# Fail2Ban
# ---------------------------------------------------------------------------

def get_fail2ban_status() -> Dict[str, Any]:
    """Return overall Fail2Ban status and list of jails."""
    stdout, stderr, rc = _run(["fail2ban-client", "status"])
    if rc != 0:
        error_text = stderr.strip() or "fail2ban-client returned a non-zero exit code"
        # For Python tracebacks the meaningful line is always the last one
        last_line = next(
            (l.strip() for l in reversed(error_text.splitlines()) if l.strip()),
            error_text,
        )
        return {"available": False, "error": last_line}

    jails: List[str] = []
    for line in stdout.splitlines():
        if "Jail list:" in line:
            raw = line.split(":", 1)[1].strip()
            jails = [j.strip() for j in raw.split(",") if j.strip()]
            break

    return {"available": True, "jails": jails}


def get_fail2ban_jail(jail: str) -> Dict[str, Any]:
    """Return detailed status for a single jail."""
    stdout, stderr, rc = _run(["fail2ban-client", "status", jail])
    if rc != 0:
        return {"error": stderr.strip()}

    info: Dict[str, Any] = {"name": jail, "currently_failed": 0, "total_failed": 0,
                             "currently_banned": 0, "total_banned": 0, "banned_ips": []}
    for line in stdout.splitlines():
        line = line.strip()
        if "Currently failed:" in line:
            info["currently_failed"] = int(re.search(r"\d+", line).group())  # type: ignore[union-attr]
        elif "Total failed:" in line:
            info["total_failed"] = int(re.search(r"\d+", line).group())  # type: ignore[union-attr]
        elif "Currently banned:" in line:
            info["currently_banned"] = int(re.search(r"\d+", line).group())  # type: ignore[union-attr]
        elif "Total banned:" in line:
            info["total_banned"] = int(re.search(r"\d+", line).group())  # type: ignore[union-attr]
        elif "Banned IP list:" in line:
            raw = line.split(":", 1)[1].strip()
            info["banned_ips"] = [ip.strip() for ip in raw.split() if ip.strip()]
    return info


def get_all_fail2ban_jails() -> Dict[str, Any]:
    """Return status for all jails."""
    status = get_fail2ban_status()
    if not status.get("available"):
        return status

    jails_detail = []
    for jail in status["jails"]:
        jails_detail.append(get_fail2ban_jail(jail))

    return {"available": True, "jails": jails_detail}


def unban_ip(jail: str, ip: str) -> Dict[str, Any]:
    """Unban an IP address from a jail."""
    # Validate IP format to prevent injection
    if not re.match(r"^[\d.:a-fA-F/]+$", ip):
        return {"success": False, "error": "Invalid IP address format"}
    if not re.match(r"^[a-zA-Z0-9_-]+$", jail):
        return {"success": False, "error": "Invalid jail name"}

    _, stderr, rc = _run(["fail2ban-client", "set", jail, "unbanip", ip])
    if rc != 0:
        return {"success": False, "error": stderr.strip()}
    return {"success": True}


# ---------------------------------------------------------------------------
# Package / CVE scanner
# ---------------------------------------------------------------------------

def get_upgradeable_packages() -> Dict[str, Any]:
    """Return list of upgradeable packages, separated into security and regular updates."""
    # Refresh cache (non-blocking best-effort)
    _run(["apt-get", "update", "-qq"], timeout=60)

    stdout, stderr, rc = _run(
        ["apt-get", "--just-print", "upgrade"],
        timeout=30,
    )

    if rc not in (0, 1):
        return {"available": False, "error": stderr.strip()}

    # Parse "Inst <package> [<current>] (<new> <origin>)" lines
    packages: List[Dict[str, Any]] = []
    security_re = re.compile(r"-security", re.IGNORECASE)

    for line in stdout.splitlines():
        if not line.startswith("Inst "):
            continue
        parts = line.split()
        name = parts[1] if len(parts) > 1 else "?"
        current = ""
        new_ver = ""
        origin = ""

        # Extract current version [...]
        m_cur = re.search(r"\[([^\]]+)\]", line)
        if m_cur:
            current = m_cur.group(1)

        # Extract new version and origin (...)
        m_new = re.search(r"\(([^)]+)\)", line)
        if m_new:
            inner = m_new.group(1)
            tokens = inner.split()
            new_ver = tokens[0] if tokens else ""
            origin = " ".join(tokens[1:]) if len(tokens) > 1 else ""

        is_security = bool(security_re.search(origin))
        packages.append({
            "name": name,
            "current_version": current,
            "new_version": new_ver,
            "origin": origin,
            "is_security": is_security,
        })

    security_count = sum(1 for p in packages if p["is_security"])
    return {
        "available": True,
        "total": len(packages),
        "security_updates": security_count,
        "packages": packages,
    }


# ---------------------------------------------------------------------------
# SSL / TLS certificates
# ---------------------------------------------------------------------------

_CERT_SEARCH_DIRS = [
    "/etc/ssl/certs",
    "/etc/letsencrypt/live",
    "/etc/nginx/ssl",
    "/etc/apache2/ssl",
    "/etc/pki/tls/certs",
    "/usr/local/share/ca-certificates",
]

_CERT_EXTENSIONS = ("*.pem", "*.crt", "*.cer")


def _parse_cert(path: str) -> Optional[Dict[str, Any]]:
    """Extract subject, issuer and expiry from a certificate file."""
    stdout, _, rc = _run(
        ["openssl", "x509", "-in", path, "-noout",
         "-subject", "-issuer", "-dates", "-fingerprint"],
        timeout=5,
    )
    if rc != 0:
        return None

    info: Dict[str, Any] = {"path": path}
    for line in stdout.splitlines():
        if line.startswith("subject="):
            info["subject"] = line[len("subject="):].strip()
        elif line.startswith("issuer="):
            info["issuer"] = line[len("issuer="):].strip()
        elif line.startswith("notBefore="):
            info["not_before"] = line[len("notBefore="):].strip()
        elif line.startswith("notAfter="):
            info["not_after"] = line[len("notAfter="):].strip()
        elif "Fingerprint=" in line:
            info["fingerprint"] = line.split("=", 1)[1].strip()

    # Calculate days until expiry
    not_after = info.get("not_after", "")
    if not_after:
        try:
            expiry_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
            now = datetime.now(tz=timezone.utc)
            info["days_until_expiry"] = (expiry_dt - now).days
            info["expired"] = info["days_until_expiry"] < 0
        except ValueError:
            info["days_until_expiry"] = None
            info["expired"] = None

    return info


def get_certificates() -> Dict[str, Any]:
    """Scan common certificate directories and return cert info."""
    certs: List[Dict[str, Any]] = []
    seen: set = set()

    for directory in _CERT_SEARCH_DIRS:
        if not os.path.isdir(directory):
            continue
        for ext in _CERT_EXTENSIONS:
            for path in glob.glob(os.path.join(directory, "**", ext), recursive=True):
                real = os.path.realpath(path)
                if real in seen:
                    continue
                seen.add(real)
                cert = _parse_cert(path)
                if cert:
                    certs.append(cert)

    expiring_soon = sum(
        1 for c in certs
        if c.get("days_until_expiry") is not None and 0 <= c["days_until_expiry"] <= 30
    )
    expired = sum(1 for c in certs if c.get("expired") is True)

    return {
        "total": len(certs),
        "expired": expired,
        "expiring_soon": expiring_soon,
        "certificates": certs,
    }


# ---------------------------------------------------------------------------
# Open ports
# ---------------------------------------------------------------------------

def get_open_ports() -> Dict[str, Any]:
    """Return listening TCP/UDP ports with process information."""
    stdout, stderr, rc = _run(["ss", "-tlnpu"])
    if rc != 0:
        return {"available": False, "error": stderr.strip()}

    ports: List[Dict[str, Any]] = []
    lines = stdout.splitlines()

    for line in lines[1:]:  # skip header
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 5:
            continue

        proto = parts[0].lower()  # tcp / udp
        state = parts[1] if proto == "tcp" else "listen"
        local_address = parts[4]

        # Split address:port (handle IPv6 brackets)
        if local_address.startswith("["):
            m = re.match(r"\[(.+)\]:(\d+|\*)", local_address)
            if m:
                addr, port = m.group(1), m.group(2)
            else:
                addr, port = local_address, "?"
        elif ":" in local_address:
            addr, port = local_address.rsplit(":", 1)
        else:
            addr, port = local_address, "?"

        # Extract process info from the last column if available
        process = ""
        for part in parts[5:]:
            if 'users:' in part or part.startswith('('):
                # Format: users:(("sshd",pid=1234,fd=3))
                m = re.search(r'"([^"]+)"', part)
                if m:
                    process = m.group(1)
                pid_m = re.search(r"pid=(\d+)", part)
                pid = pid_m.group(1) if pid_m else ""
                if pid:
                    process = f"{process} (pid {pid})"
                break

        ports.append({
            "proto": proto,
            "state": state,
            "address": addr,
            "port": port,
            "process": process,
        })

    return {"available": True, "total": len(ports), "ports": ports}


# ---------------------------------------------------------------------------
# CVE Scanner (via OSV.dev API)
# ---------------------------------------------------------------------------

_OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
_SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}


def _get_ecosystem() -> str:
    """Detect OS ecosystem string for the OSV API (e.g. 'Debian:12', 'Ubuntu:24.04')."""
    try:
        with open("/etc/os-release") as f:
            content = f.read()
        data: Dict[str, str] = {}
        for line in content.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip('"')
        name = data.get("NAME", "").lower()
        version_id = data.get("VERSION_ID", "")
        if "ubuntu" in name:
            return f"Ubuntu:{version_id}"
        elif "debian" in name:
            major = version_id.split(".")[0] if version_id else "12"
            return f"Debian:{major}"
    except Exception:
        pass
    return "Debian:12"


def _get_dpkg_packages() -> List[Dict[str, str]]:
    """Return installed Debian/Ubuntu packages (name + version) via dpkg-query."""
    stdout, _, rc = _run(
        ["dpkg-query", "-W", "-f=${Package}\t${Version}\n"],
        timeout=30,
    )
    if rc != 0:
        return []
    packages: List[Dict[str, str]] = []
    for line in stdout.splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 2 and parts[0] and parts[1] and parts[1] not in ("<none>", "-"):
            # Strip epoch prefix (e.g. "2:1.2.3-1" → "1.2.3-1")
            ver = re.sub(r"^\d+:", "", parts[1])
            packages.append({"name": parts[0], "version": ver})
    return packages


def scan_cves(limit: int = 300) -> Dict[str, Any]:
    """Scan installed packages against the OSV.dev vulnerability database."""
    if not shutil.which("dpkg-query"):
        return {
            "available": False,
            "error": "dpkg-query not found – CVE scanning requires a Debian/Ubuntu system.",
        }

    ecosystem = _get_ecosystem()
    packages = _get_dpkg_packages()

    if not packages:
        return {"available": False, "error": "Could not retrieve installed package list."}

    packages = packages[:limit]
    all_vulns: List[Dict[str, Any]] = []

    for i in range(0, len(packages), 100):
        batch = packages[i : i + 100]
        queries = [
            {
                "version": pkg["version"],
                "package": {"name": pkg["name"], "ecosystem": ecosystem},
            }
            for pkg in batch
        ]
        payload = json.dumps({"queries": queries}).encode()
        req = urllib.request.Request(
            _OSV_BATCH_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
        except Exception:
            continue

        for j, res in enumerate(result.get("results", [])):
            for vuln in res.get("vulns", []):
                pkg = batch[j]
                severity = "unknown"
                score: Optional[float] = None

                for s in vuln.get("severity", []):
                    if s.get("type") in ("CVSS_V3", "CVSS_V4"):
                        try:
                            score = float(s["score"])
                            if score >= 9.0:
                                severity = "critical"
                            elif score >= 7.0:
                                severity = "high"
                            elif score >= 4.0:
                                severity = "medium"
                            else:
                                severity = "low"
                        except (ValueError, KeyError):
                            pass
                        break
                    elif s.get("type") == "CVSS_V2" and score is None:
                        try:
                            score = float(s["score"])
                            severity = "high" if score >= 7.0 else ("medium" if score >= 4.0 else "low")
                        except (ValueError, KeyError):
                            pass

                aliases = [a for a in vuln.get("aliases", []) if a.startswith("CVE-")]
                cve_id = aliases[0] if aliases else vuln.get("id", "")

                all_vulns.append({
                    "package": pkg["name"],
                    "version": pkg["version"],
                    "vuln_id": vuln.get("id", ""),
                    "cve_id": cve_id,
                    "summary": vuln.get("summary", ""),
                    "severity": severity,
                    "cvss_score": score,
                    "published": (vuln.get("published", "") or "")[:10],
                })

    all_vulns.sort(
        key=lambda v: (_SEV_ORDER.get(v["severity"], 4), -(v["cvss_score"] or 0))
    )

    severity_counts: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
    for v in all_vulns:
        severity_counts[v["severity"]] = severity_counts.get(v["severity"], 0) + 1

    return {
        "available": True,
        "ecosystem": ecosystem,
        "packages_scanned": len(packages),
        "total_vulns": len(all_vulns),
        "severity_counts": severity_counts,
        "vulnerabilities": all_vulns,
    }
