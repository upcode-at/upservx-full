"""Security primitives for authenticated, encrypted cluster communication.

Cluster requests use HMAC-SHA256 signatures over the HTTP method, raw target,
body digest, sender identity, key identifier, timestamp, and a unique nonce.
Verified nonces are persisted under a file lock so replay protection works
across all Uvicorn worker processes.

Inter-node HTTP clients accept HTTPS URLs only. Each Upcode Harbor node owns a local
certificate authority and a server certificate. Peers obtain and pin that CA
through a one-time HTTPS bootstrap response whose contents are authenticated by
the cluster enrollment key.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import socket
import ssl
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

import httpx

from lib.secure_store import ensure_config_directory


CLUSTER_TLS_PORT = int(os.getenv("UPCODE_HARBOR_CLUSTER_TLS_PORT", "9501"))
CLUSTER_SECURITY_DIR = Path(
    os.getenv("UPCODE_HARBOR_CLUSTER_SECURITY_DIR", "/etc/upcode-harbor/cluster-security")
)
NODE_CA_CERT_FILE = CLUSTER_SECURITY_DIR / "node-ca.pem"
NODE_CA_KEY_FILE = CLUSTER_SECURITY_DIR / "node-ca.key"
NODE_CERT_FILE = CLUSTER_SECURITY_DIR / "node.pem"
NODE_KEY_FILE = CLUSTER_SECURITY_DIR / "node.key"

CONFIG_DIR = Path(os.getenv("UPCODE_HARBOR_CONFIG_DIR", "/etc/upcode-harbor"))
MASTER_CONFIG_FILE = CONFIG_DIR / "master"
CHILD_CONFIG_FILE = CONFIG_DIR / "child"
NODES_DIR = CONFIG_DIR / "nodes"
NONCE_CACHE_FILE = CONFIG_DIR / "cluster-nonces.json"
NONCE_LOCK_FILE = CONFIG_DIR / "cluster-nonces.lock"

SIGNATURE_VERSION = "1"
MAX_CLOCK_SKEW_SECONDS = int(
    os.getenv("UPCODE_HARBOR_CLUSTER_MAX_CLOCK_SKEW_SECONDS", "60")
)
DEFAULT_KEY_OVERLAP_SECONDS = int(
    os.getenv("UPCODE_HARBOR_CLUSTER_KEY_OVERLAP_SECONDS", "86400")
)

HEADER_VERSION = "X-Upcode-Harbor-Signature-Version"
HEADER_KEY_ID = "X-Upcode-Harbor-Key-Id"
HEADER_TIMESTAMP = "X-Upcode-Harbor-Timestamp"
HEADER_NONCE = "X-Upcode-Harbor-Nonce"
HEADER_NODE = "X-Upcode-Harbor-Node"
HEADER_SIGNATURE = "X-Upcode-Harbor-Signature"

_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_NODE_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,251}[A-Za-z0-9])?$")


class ClusterSecurityError(Exception):
    """A fail-closed cluster authentication or transport error."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class VerifiedClusterRequest:
    """Identity and key metadata returned after signature verification."""

    node_id: str
    key_id: str
    timestamp: int
    nonce: str


@dataclass(frozen=True)
class NodeTLSMaterial:
    """Paths and CA contents used by the dedicated cluster HTTPS listener."""

    ca_cert_file: str
    cert_file: str
    key_file: str
    ca_certificate: str


def derive_key_id(key: str) -> str:
    """Derive a non-secret stable identifier for a cluster key."""

    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def normalize_cluster_port(port: int | str | None) -> int:
    """Map the legacy HTTP port to the dedicated secure cluster port."""

    if port is None:
        return CLUSTER_TLS_PORT
    parsed = int(port)
    return CLUSTER_TLS_PORT if parsed == 9500 else parsed


def cluster_url(host: str, port: int | str | None, path: str) -> str:
    """Build an HTTPS-only peer URL."""

    if not path.startswith("/"):
        raise ClusterSecurityError("Cluster path must be absolute", 500)
    clean_host = host.strip()
    if not clean_host or "://" in clean_host or "/" in clean_host:
        raise ClusterSecurityError("Invalid cluster host", 500)
    try:
        parsed_ip = ipaddress.ip_address(clean_host.strip("[]"))
        if parsed_ip.version == 6:
            clean_host = f"[{parsed_ip.compressed}]"
    except ValueError:
        pass
    return f"https://{clean_host}:{normalize_cluster_port(port)}{path}"


def _raw_target(url: httpx.URL) -> str:
    return url.raw_path.decode("ascii")


def _canonical_message(
    method: str,
    raw_target: str,
    body: bytes,
    node_id: str,
    key_id: str,
    timestamp: int,
    nonce: str,
) -> bytes:
    body_digest = hashlib.sha256(body).hexdigest()
    components = (
        SIGNATURE_VERSION,
        method.upper(),
        raw_target,
        body_digest,
        node_id,
        key_id,
        str(timestamp),
        nonce,
    )
    return "\n".join(components).encode("utf-8")


def sign_cluster_headers(
    key: str,
    method: str,
    raw_target: str,
    body: bytes = b"",
    *,
    node_id: str | None = None,
    key_id: str | None = None,
    timestamp: int | None = None,
    nonce: str | None = None,
) -> dict[str, str]:
    """Return HMAC headers for one exact request representation."""

    if not key:
        raise ClusterSecurityError("Cluster key is unavailable", 500)
    sender = node_id or get_local_node_id()
    if not _NODE_RE.fullmatch(sender):
        raise ClusterSecurityError("Invalid local cluster node identity", 500)
    resolved_key_id = key_id or derive_key_id(key)
    resolved_timestamp = int(time.time()) if timestamp is None else int(timestamp)
    resolved_nonce = nonce or secrets.token_urlsafe(24)
    canonical = _canonical_message(
        method,
        raw_target,
        body,
        sender,
        resolved_key_id,
        resolved_timestamp,
        resolved_nonce,
    )
    signature = hmac.new(
        key.encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()
    return {
        HEADER_VERSION: SIGNATURE_VERSION,
        HEADER_KEY_ID: resolved_key_id,
        HEADER_TIMESTAMP: str(resolved_timestamp),
        HEADER_NONCE: resolved_nonce,
        HEADER_NODE: sender,
        HEADER_SIGNATURE: signature,
    }


def has_cluster_signature(headers: Mapping[str, str]) -> bool:
    """Return whether any cluster signature header is present."""

    lowered = {name.lower() for name in headers}
    return any(
        header.lower() in lowered
        for header in (
            HEADER_VERSION,
            HEADER_KEY_ID,
            HEADER_TIMESTAMP,
            HEADER_NONCE,
            HEADER_NODE,
            HEADER_SIGNATURE,
        )
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _write_json_atomic(path: Path, value: Any) -> None:
    ensure_config_directory(path.parent)
    fd, temporary_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
        text=True,
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(value, file, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, 0o600)
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


def write_cluster_json(path: str | Path, value: Any) -> None:
    """Persist cluster configuration atomically with owner-only permissions."""

    _write_json_atomic(Path(path), value)


def _write_bytes_atomic(path: Path, value: bytes, mode: int) -> None:
    """Replace a certificate or key without a permissive creation window."""

    ensure_config_directory(path.parent)
    fd, temporary_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
    )
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as file:
            file.write(value)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
        os.chmod(path, mode)
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


def _key_entries_from_config(config: Mapping[str, Any], *, child: bool) -> dict[str, str]:
    now = int(time.time())
    entries: dict[str, str] = {}
    current_key = config.get("cluster_key") if child else config.get("key")
    if child and not current_key:
        current_key = config.get("key")
    if isinstance(current_key, str) and current_key:
        configured_id = (
            config.get("cluster_key_id") if child else config.get("key_id")
        )
        entries[str(configured_id or derive_key_id(current_key))] = current_key

    for entry in config.get("previous_keys", []):
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        valid_until = entry.get("valid_until")
        if not isinstance(key, str) or not key:
            continue
        try:
            if valid_until is not None and int(valid_until) < now:
                continue
        except (TypeError, ValueError):
            continue
        entries[str(entry.get("key_id") or derive_key_id(key))] = key

    pending = config.get("pending_key")
    if isinstance(pending, dict):
        key = pending.get("key")
        if isinstance(key, str) and key:
            entries[str(pending.get("key_id") or derive_key_id(key))] = key
    return entries


def load_cluster_keyring() -> dict[str, str]:
    """Load current, overlapping, and pending verification keys."""

    master = _read_json(MASTER_CONFIG_FILE)
    if master:
        return _key_entries_from_config(master, child=False)
    child = _read_json(CHILD_CONFIG_FILE)
    if child:
        return _key_entries_from_config(child, child=True)
    return {}


def get_current_cluster_key() -> tuple[str, str]:
    """Return the current signing key and key identifier."""

    master = _read_json(MASTER_CONFIG_FILE)
    if master:
        key = master.get("key")
        if isinstance(key, str) and key:
            return key, str(master.get("key_id") or derive_key_id(key))
    child = _read_json(CHILD_CONFIG_FILE)
    if child:
        key = child.get("cluster_key") or child.get("key")
        if isinstance(key, str) and key:
            return key, str(
                child.get("cluster_key_id")
                or child.get("key_id")
                or derive_key_id(key)
            )
    raise ClusterSecurityError("This node has no active cluster key", 503)


def get_local_node_id() -> str:
    """Return the stable node identity included in signed requests."""

    child = _read_json(CHILD_CONFIG_FILE)
    if child:
        assigned = child.get("assigned_hostname")
        if isinstance(assigned, str) and assigned:
            return assigned
    return socket.gethostname()


def _record_nonce_once(
    key_id: str,
    nonce: str,
    timestamp: int,
    *,
    now: int,
) -> None:
    """Persist a nonce atomically and reject an existing nonce."""

    try:
        ensure_config_directory(NONCE_LOCK_FILE.parent)
        descriptor = os.open(NONCE_LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            cache = _read_json(NONCE_CACHE_FILE) or {}
            seen = cache.get("seen", {})
            if not isinstance(seen, dict):
                seen = {}
            cutoff = now - (MAX_CLOCK_SKEW_SECONDS * 2)
            seen = {
                token: value
                for token, value in seen.items()
                if isinstance(value, int) and value >= cutoff
            }
            replay_token = f"{key_id}:{nonce}"
            if replay_token in seen:
                raise ClusterSecurityError("Replayed cluster request")
            seen[replay_token] = timestamp
            _write_json_atomic(NONCE_CACHE_FILE, {"seen": seen})
    except ClusterSecurityError:
        raise
    except OSError as error:
        raise ClusterSecurityError(
            "Cluster replay cache is unavailable",
            503,
        ) from error


def _known_peer(node_id: str, raw_target: str) -> bool:
    """Check the signed sender against persisted cluster membership."""

    path = raw_target.split("?", 1)[0]
    if path in {"/cluster/bootstrap", "/cluster/register"}:
        return True

    master = _read_json(MASTER_CONFIG_FILE)
    if master:
        try:
            for node_file in NODES_DIR.glob("*.json"):
                node = _read_json(node_file)
                if not node:
                    continue
                identities = {
                    node.get("hostname"),
                    node.get("assigned_hostname"),
                    node.get("original_hostname"),
                }
                if node_id in identities:
                    return True
        except OSError:
            return False
        return False

    child = _read_json(CHILD_CONFIG_FILE)
    if child:
        expected = child.get("master_hostname")
        if isinstance(expected, str) and expected:
            return hmac.compare_digest(expected, node_id)

        # Authenticated migration for legacy child configs: pin the first
        # HMAC-verified master identity and require it for subsequent requests.
        migrated = dict(child)
        migrated["master_hostname"] = node_id
        try:
            _write_json_atomic(CHILD_CONFIG_FILE, migrated)
            return True
        except OSError:
            return False
    return False


def verify_cluster_signature(
    method: str,
    raw_target: str,
    body: bytes,
    headers: Mapping[str, str],
    *,
    keyring: Mapping[str, str] | None = None,
    now: int | None = None,
    check_replay: bool = True,
    check_peer: bool = True,
) -> VerifiedClusterRequest:
    """Verify HMAC, clock window, replay state, and peer identity."""

    lowered = {name.lower(): value for name, value in headers.items()}

    def required(name: str) -> str:
        value = lowered.get(name.lower())
        if not value:
            raise ClusterSecurityError("Incomplete cluster signature")
        return value

    if required(HEADER_VERSION) != SIGNATURE_VERSION:
        raise ClusterSecurityError("Unsupported cluster signature version")

    key_id = required(HEADER_KEY_ID)
    timestamp_value = required(HEADER_TIMESTAMP)
    nonce = required(HEADER_NONCE)
    node_id = required(HEADER_NODE)
    supplied_signature = required(HEADER_SIGNATURE)

    if not _NONCE_RE.fullmatch(nonce):
        raise ClusterSecurityError("Invalid cluster request nonce")
    if not _NODE_RE.fullmatch(node_id):
        raise ClusterSecurityError("Invalid cluster node identity")
    if not re.fullmatch(r"[0-9a-f]{64}", supplied_signature):
        raise ClusterSecurityError("Invalid cluster signature encoding")

    try:
        timestamp = int(timestamp_value)
    except ValueError as error:
        raise ClusterSecurityError("Invalid cluster request timestamp") from error
    current_time = int(time.time()) if now is None else int(now)
    if abs(current_time - timestamp) > MAX_CLOCK_SKEW_SECONDS:
        raise ClusterSecurityError("Cluster request timestamp is outside the allowed window")

    keys = dict(keyring) if keyring is not None else load_cluster_keyring()
    key = keys.get(key_id)
    if not key:
        raise ClusterSecurityError("Unknown or expired cluster key")

    canonical = _canonical_message(
        method,
        raw_target,
        body,
        node_id,
        key_id,
        timestamp,
        nonce,
    )
    expected_signature = hmac.new(
        key.encode("utf-8"),
        canonical,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, supplied_signature):
        raise ClusterSecurityError("Invalid cluster request signature")

    if check_peer and not _known_peer(node_id, raw_target):
        raise ClusterSecurityError("Unknown cluster peer")
    if check_replay:
        _record_nonce_once(
            key_id,
            nonce,
            timestamp,
            now=current_time,
        )

    return VerifiedClusterRequest(
        node_id=node_id,
        key_id=key_id,
        timestamp=timestamp,
        nonce=nonce,
    )


def _bootstrap_proof_message(
    request_nonce: str,
    node_id: str,
    port: int,
    ca_certificate: str,
    timestamp: int,
) -> bytes:
    ca_digest = hashlib.sha256(ca_certificate.encode("utf-8")).hexdigest()
    return (
        f"bootstrap-response\n{request_nonce}\n{node_id}\n{port}\n"
        f"{ca_digest}\n{timestamp}"
    ).encode("utf-8")


def create_bootstrap_response(
    key: str,
    request_nonce: str,
    *,
    timestamp: int | None = None,
) -> dict[str, Any]:
    """Create a token-authenticated response containing this node's CA."""

    material = ensure_node_tls()
    resolved_timestamp = int(time.time()) if timestamp is None else int(timestamp)
    node_id = get_local_node_id()
    message = _bootstrap_proof_message(
        request_nonce,
        node_id,
        CLUSTER_TLS_PORT,
        material.ca_certificate,
        resolved_timestamp,
    )
    proof = hmac.new(
        key.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return {
        "node_id": node_id,
        "port": CLUSTER_TLS_PORT,
        "ca_certificate": material.ca_certificate,
        "timestamp": resolved_timestamp,
        "request_nonce": request_nonce,
        "proof": proof,
    }


def verify_bootstrap_response(
    key: str,
    payload: Mapping[str, Any],
    request_nonce: str,
    *,
    expected_node_id: str | None = None,
    now: int | None = None,
) -> tuple[str, str, int]:
    """Verify a bootstrap proof and return CA, peer identity, and secure port."""

    try:
        node_id = str(payload["node_id"])
        port = int(payload["port"])
        ca_certificate = str(payload["ca_certificate"])
        timestamp = int(payload["timestamp"])
        response_nonce = str(payload["request_nonce"])
        proof = str(payload["proof"])
    except (KeyError, TypeError, ValueError) as error:
        raise ClusterSecurityError("Invalid cluster bootstrap response") from error

    if response_nonce != request_nonce:
        raise ClusterSecurityError("Cluster bootstrap nonce mismatch")
    if expected_node_id and not hmac.compare_digest(expected_node_id, node_id):
        raise ClusterSecurityError("Cluster bootstrap peer identity mismatch")
    current_time = int(time.time()) if now is None else int(now)
    if abs(current_time - timestamp) > MAX_CLOCK_SKEW_SECONDS:
        raise ClusterSecurityError("Cluster bootstrap response has expired")
    expected = hmac.new(
        key.encode("utf-8"),
        _bootstrap_proof_message(
            request_nonce,
            node_id,
            port,
            ca_certificate,
            timestamp,
        ),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, proof):
        raise ClusterSecurityError("Invalid cluster bootstrap proof")
    try:
        ssl.create_default_context(cadata=ca_certificate)
    except ssl.SSLError as error:
        raise ClusterSecurityError("Invalid peer CA certificate") from error
    return ca_certificate, node_id, normalize_cluster_port(port)


def _ssl_context_for_ca(ca_certificate: str) -> ssl.SSLContext:
    if not ca_certificate:
        raise ClusterSecurityError("Peer CA certificate is unavailable", 503)
    try:
        context = ssl.create_default_context(cadata=ca_certificate)
    except ssl.SSLError as error:
        raise ClusterSecurityError("Peer CA certificate is invalid", 503) from error
    # The CA is pinned to one node. Disabling DNS/IP matching permits changing
    # management addresses without weakening certificate-chain validation.
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def _prepare_signed_request(
    client: httpx.Client | httpx.AsyncClient,
    method: str,
    url: str,
    *,
    key: str,
    key_id: str | None,
    node_id: str | None,
    json_data: Any,
    content: bytes | str | None,
    params: Mapping[str, Any] | None,
    headers: Mapping[str, str] | None,
) -> httpx.Request:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https":
        raise ClusterSecurityError("Unencrypted cluster transport is forbidden", 500)
    request_headers = dict(headers or {})
    if json_data is not None:
        body = json.dumps(
            json_data,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    elif isinstance(content, str):
        body = content.encode("utf-8")
    else:
        body = content or b""
    request = client.build_request(
        method,
        url,
        params=params,
        content=body,
        headers=request_headers,
    )
    request.headers.update(
        sign_cluster_headers(
            key,
            method,
            _raw_target(request.url),
            body,
            node_id=node_id,
            key_id=key_id,
        )
    )
    return request


async def signed_cluster_request(
    method: str,
    url: str,
    *,
    key: str | None = None,
    key_id: str | None = None,
    node_id: str | None = None,
    ca_certificate: str,
    json_data: Any = None,
    content: bytes | str | None = None,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 10.0,
) -> httpx.Response:
    """Send a signed HTTPS request and verify the pinned peer CA."""

    resolved_key, current_key_id = (
        (key, key_id or derive_key_id(key))
        if key is not None
        else get_current_cluster_key()
    )
    async with httpx.AsyncClient(
        verify=_ssl_context_for_ca(ca_certificate),
        timeout=timeout,
    ) as client:
        request = _prepare_signed_request(
            client,
            method,
            url,
            key=resolved_key,
            key_id=key_id or current_key_id,
            node_id=node_id,
            json_data=json_data,
            content=content,
            params=params,
            headers=headers,
        )
        return await client.send(request)


def signed_cluster_request_sync(
    method: str,
    url: str,
    *,
    key: str | None = None,
    key_id: str | None = None,
    node_id: str | None = None,
    ca_certificate: str,
    json_data: Any = None,
    content: bytes | str | None = None,
    params: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 10.0,
) -> httpx.Response:
    """Synchronous equivalent used by HA background threads."""

    resolved_key, current_key_id = (
        (key, key_id or derive_key_id(key))
        if key is not None
        else get_current_cluster_key()
    )
    with httpx.Client(
        verify=_ssl_context_for_ca(ca_certificate),
        timeout=timeout,
    ) as client:
        request = _prepare_signed_request(
            client,
            method,
            url,
            key=resolved_key,
            key_id=key_id or current_key_id,
            node_id=node_id,
            json_data=json_data,
            content=content,
            params=params,
            headers=headers,
        )
        return client.send(request)


async def bootstrap_peer_ca(
    host: str,
    port: int | str | None,
    key: str,
    *,
    expected_node_id: str | None = None,
    node_id: str | None = None,
    timeout: float = 10.0,
) -> tuple[str, str, int]:
    """Obtain a peer CA through an HMAC-authenticated TLS bootstrap."""

    url = cluster_url(host, port, "/cluster/bootstrap")
    body = {"node_id": node_id or get_local_node_id()}
    async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
        request = _prepare_signed_request(
            client,
            "POST",
            url,
            key=key,
            key_id=derive_key_id(key),
            node_id=node_id,
            json_data=body,
            content=None,
            params=None,
            headers=None,
        )
        request_nonce = request.headers[HEADER_NONCE]
        response = await client.send(request)
    response.raise_for_status()
    return verify_bootstrap_response(
        key,
        response.json(),
        request_nonce,
        expected_node_id=expected_node_id,
    )


def bootstrap_peer_ca_sync(
    host: str,
    port: int | str | None,
    key: str,
    *,
    expected_node_id: str | None = None,
    node_id: str | None = None,
    timeout: float = 10.0,
) -> tuple[str, str, int]:
    """Synchronous peer CA bootstrap for HA background threads."""

    url = cluster_url(host, port, "/cluster/bootstrap")
    body = {"node_id": node_id or get_local_node_id()}
    with httpx.Client(verify=False, timeout=timeout) as client:
        request = _prepare_signed_request(
            client,
            "POST",
            url,
            key=key,
            key_id=derive_key_id(key),
            node_id=node_id,
            json_data=body,
            content=None,
            params=None,
            headers=None,
        )
        request_nonce = request.headers[HEADER_NONCE]
        response = client.send(request)
    response.raise_for_status()
    return verify_bootstrap_response(
        key,
        response.json(),
        request_nonce,
        expected_node_id=expected_node_id,
    )


def _certificate_is_current(path: Path, ca_path: Path) -> bool:
    try:
        from cryptography import x509

        cert = x509.load_pem_x509_certificate(path.read_bytes())
        ca = x509.load_pem_x509_certificate(ca_path.read_bytes())
        now = datetime.now(timezone.utc)
        return (
            cert.not_valid_after_utc > now + timedelta(days=30)
            and cert.issuer == ca.subject
        )
    except (OSError, ValueError):
        return False


def ensure_node_tls() -> NodeTLSMaterial:
    """Create or renew node-local CA and server certificate material."""

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    CLUSTER_SECURITY_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CLUSTER_SECURITY_DIR, 0o700)
    now = datetime.now(timezone.utc)

    if not NODE_CA_CERT_FILE.exists() or not NODE_CA_KEY_FILE.exists():
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        ca_name = x509.Name(
            [
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Upcode Harbor"),
                x509.NameAttribute(
                    NameOID.COMMON_NAME,
                    f"Upcode Harbor node CA {socket.gethostname()}",
                ),
            ]
        )
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_name)
            .issuer_name(ca_name)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                True,
            )
            .sign(ca_key, hashes.SHA256())
        )
        _write_bytes_atomic(
            NODE_CA_KEY_FILE,
            ca_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            0o600,
        )
        _write_bytes_atomic(
            NODE_CA_CERT_FILE,
            ca_cert.public_bytes(serialization.Encoding.PEM),
            0o600,
        )

    if (
        not NODE_CERT_FILE.exists()
        or not NODE_KEY_FILE.exists()
        or not _certificate_is_current(NODE_CERT_FILE, NODE_CA_CERT_FILE)
    ):
        ca_key = serialization.load_pem_private_key(
            NODE_CA_KEY_FILE.read_bytes(),
            password=None,
        )
        ca_cert = x509.load_pem_x509_certificate(NODE_CA_CERT_FILE.read_bytes())
        node_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        hostname = socket.gethostname()
        subject = x509.Name(
            [
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Upcode Harbor"),
                x509.NameAttribute(NameOID.COMMON_NAME, hostname),
            ]
        )
        san_entries: list[x509.GeneralName] = [
            x509.DNSName(hostname),
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            x509.IPAddress(ipaddress.ip_address("::1")),
        ]
        node_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(node_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=825))
            .add_extension(x509.SubjectAlternativeName(san_entries), False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        _write_bytes_atomic(
            NODE_KEY_FILE,
            node_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            0o600,
        )
        _write_bytes_atomic(
            NODE_CERT_FILE,
            node_cert.public_bytes(serialization.Encoding.PEM),
            0o600,
        )

    return NodeTLSMaterial(
        ca_cert_file=str(NODE_CA_CERT_FILE),
        cert_file=str(NODE_CERT_FILE),
        key_file=str(NODE_KEY_FILE),
        ca_certificate=NODE_CA_CERT_FILE.read_text(encoding="utf-8"),
    )


def install_rotated_child_key(
    new_key: str,
    new_key_id: str,
    previous_valid_until: int,
) -> None:
    """Install a master-distributed key and retain the old key temporarily."""

    config = _read_json(CHILD_CONFIG_FILE)
    if not config:
        raise ClusterSecurityError("Child cluster configuration is unavailable", 503)
    current_key = config.get("cluster_key") or config.get("key")
    current_id = (
        config.get("cluster_key_id")
        or config.get("key_id")
        or (derive_key_id(current_key) if current_key else None)
    )
    if current_key and current_id and current_id != new_key_id:
        previous = [
            entry
            for entry in config.get("previous_keys", [])
            if isinstance(entry, dict) and entry.get("key_id") != current_id
        ]
        previous.append(
            {
                "key_id": current_id,
                "key": current_key,
                "valid_until": int(previous_valid_until),
            }
        )
        config["previous_keys"] = previous
    config["cluster_key"] = new_key
    config["key"] = new_key
    config["cluster_key_id"] = new_key_id
    config.pop("key_id", None)
    _write_json_atomic(CHILD_CONFIG_FILE, config)
