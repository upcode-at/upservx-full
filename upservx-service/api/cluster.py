from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional
import asyncio
import ipaddress
import re
import secrets
import socket
import ssl
import psutil
from datetime import datetime
import json
import os
import shutil
import subprocess
import time
import httpx
from lib.load_balancer import get_load_balancer, LoadBalancingStrategy
from lib.container_sync import get_sync_manager
from lib.metrics_collector import get_metrics_collector
from lib.logger import log_system
from lib.progress_tracker import get_progress, set_progress
from lib.crontab_manager import CrontabManager
from lib.file_lock import InterProcessFileLock
from lib.jobs import enqueue_job, find_latest_job, get_job
from lib.secure_store import ensure_config_directory, secure_read_json
from lib.cluster_security import (
    CLUSTER_TLS_PORT,
    DEFAULT_KEY_OVERLAP_SECONDS,
    HEADER_NONCE,
    ClusterSecurityError,
    bootstrap_peer_ca,
    cluster_url,
    create_bootstrap_response,
    derive_key_id,
    ensure_node_tls,
    install_rotated_child_key,
    load_cluster_keyring,
    normalize_cluster_port,
    signed_cluster_request,
    write_cluster_json,
)
from handlers.notifications import notify

def _clog(msg: str, error: bool = False) -> None:
    """Print to console AND write to activity log file."""
    print(msg)
    log_system(msg, error=error)

router = APIRouter()

# Paths for cluster configuration
UPSERVX_CONFIG_DIR = os.getenv("UPSERVX_CONFIG_DIR", "/etc/upservx")
MASTER_CONFIG_FILE = os.path.join(UPSERVX_CONFIG_DIR, "master")
CHILD_CONFIG_FILE = os.path.join(UPSERVX_CONFIG_DIR, "child")
NODES_DIR = os.path.join(UPSERVX_CONFIG_DIR, "nodes")
NODE_HOSTNAME_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,251}[A-Za-z0-9])?$"
)

class ClusterCreateRequest(BaseModel):
    cluster_name: str

class ClusterJoinRequest(BaseModel):
    master_ip: str
    token: str = Field(min_length=32)
    port: int = Field(default=CLUSTER_TLS_PORT, ge=1, le=65535)

class NodeRegistrationRequest(BaseModel):
    hostname: str = Field(
        min_length=1,
        max_length=253,
        pattern=NODE_HOSTNAME_PATTERN.pattern,
    )
    ip_address: str
    port: int = Field(ge=1, le=65535)
    tls_ca_certificate: str = Field(min_length=1, max_length=65536)
    resources: dict = Field(default_factory=dict)


class ClusterKeyRotationRequest(BaseModel):
    overlap_seconds: int = Field(
        default=DEFAULT_KEY_OVERLAP_SECONDS,
        ge=300,
        le=604800,
    )


class ClusterKeyUpdateRequest(BaseModel):
    key: str = Field(min_length=32)
    key_id: str = Field(min_length=8, max_length=64)
    previous_valid_until: int

class ClusterNode(BaseModel):
    id: str
    hostname: str
    ip_address: str
    port: int
    status: str
    role: str
    resources: dict
    last_seen: str

class ClusterInfo(BaseModel):
    is_master: bool
    is_member: bool
    master_ip: Optional[str] = None
    nodes: List[ClusterNode]

def ensure_config_dir():
    """Ensure configuration directory exists"""
    try:
        ensure_config_directory(UPSERVX_CONFIG_DIR)
        ensure_config_directory(NODES_DIR)
        _clog(f"[CLUSTER] Config directories ensured: {UPSERVX_CONFIG_DIR}, {NODES_DIR}")
        _clog(f"[CLUSTER] NODES_DIR exists: {os.path.exists(NODES_DIR)}")
        _clog(f"[CLUSTER] NODES_DIR is writable: {os.access(NODES_DIR, os.W_OK)}")
    except Exception as e:
        _clog(f"[CLUSTER] ERROR creating config directories: {e}", error=True)

        raise

def read_master_config():
    """Read master configuration file"""
    if os.path.exists(MASTER_CONFIG_FILE):
        with open(MASTER_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None

def write_master_config(config: dict):
    """Write master configuration file"""
    ensure_config_dir()
    write_cluster_json(MASTER_CONFIG_FILE, config)

def read_child_config():
    """Read child configuration file"""
    if os.path.exists(CHILD_CONFIG_FILE):
        with open(CHILD_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None

def write_child_config(config: dict):
    """Write child configuration file"""
    ensure_config_dir()
    write_cluster_json(CHILD_CONFIG_FILE, config)


def _redact_cluster_secrets(value):
    """Return debug-safe cluster configuration without enrollment secrets."""

    if isinstance(value, dict):
        return {
            key: "[redacted]" if key in {"key", "cluster_key", "token"}
            else _redact_cluster_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_cluster_secrets(item) for item in value]
    return value

def read_node_config(hostname: str):
    """Read a specific node configuration"""
    if not NODE_HOSTNAME_PATTERN.fullmatch(hostname):
        return None
    node_file = os.path.join(NODES_DIR, f"{hostname}.json")
    if os.path.exists(node_file):
        with open(node_file, 'r') as f:
            return json.load(f)
    return None

def resolve_node_for_removal(node_id: str):
    """Resolve a node reference to the stored hostname and config."""
    node_config = read_node_config(node_id)
    if node_config:
        return node_id, node_config

    for node in list_all_nodes():
        hostname = node.get("hostname")
        original_hostname = node.get("original_hostname")
        assigned_hostname = node.get("assigned_hostname")
        ip_address = node.get("ip_address")

        if node_id in {hostname, original_hostname, assigned_hostname, ip_address}:
            return hostname, node

    return None, None

def find_unique_hostname(base_hostname: str) -> str:
    """Find a unique hostname by appending -2, -3, etc. if hostname already exists"""
    hostname = base_hostname
    counter = 2
    
    while read_node_config(hostname) is not None:
        suffix = f"-{counter}"
        hostname = f"{base_hostname[:253 - len(suffix)]}{suffix}"
        counter += 1
        _clog(f"[CLUSTER] Hostname {base_hostname} exists, trying {hostname}")
    
    return hostname

def write_node_config(hostname: str, config: dict):
    """Write node configuration file"""
    if not NODE_HOSTNAME_PATTERN.fullmatch(hostname):
        raise ValueError("Invalid cluster node hostname")
    ensure_config_dir()
    node_file = os.path.join(NODES_DIR, f"{hostname}.json")
    _clog(f"[CLUSTER] Writing node config to {node_file}")
    try:
        write_cluster_json(node_file, config)
        _clog(f"[CLUSTER] Successfully wrote node config for {hostname}")
        if os.path.exists(node_file):
            _clog(f"[CLUSTER] File {node_file} exists and has {os.path.getsize(node_file)} bytes")
        else:
            _clog(f"[CLUSTER] WARNING: File {node_file} does not exist after write!")
    except Exception as e:
        _clog(f"[CLUSTER] ERROR writing node config: {e}", error=True)

        raise

def delete_node_config(hostname: str):
    """Delete node configuration file"""
    if not NODE_HOSTNAME_PATTERN.fullmatch(hostname):
        return
    node_file = os.path.join(NODES_DIR, f"{hostname}.json")
    if os.path.exists(node_file):
        os.remove(node_file)

async def notify_removed_node(node_id: str, node: dict, cluster_key: str) -> None:
    """Best-effort notification to a removed child node so it can clear its local cluster state."""
    node_ip = node.get("ip_address")
    node_port = normalize_cluster_port(node.get("port"))
    _clog(f"[CLUSTER] Notifying removed node {node_id} at {node_ip}:{node_port}")
    try:
        ca_certificate, node_port, _ = await _resolve_peer_tls(
            node,
            cluster_key,
            expected_node_id=node_id,
        )
        response = await signed_cluster_request(
            "POST",
            cluster_url(node_ip, node_port, "/cluster/force-leave"),
            key=cluster_key,
            ca_certificate=ca_certificate,
            timeout=3.0,
        )

        if response.status_code == 200:
            _clog(f"[CLUSTER] Removed node notified successfully: {node_id}")
        else:
            _clog(
                f"[CLUSTER] Failed to notify removed node {node_id}: HTTP {response.status_code}",
                error=True,
            )
    except Exception as e:
        _clog(f"[CLUSTER] Removed node {node_id} is offline or unreachable: {e}", error=True)

def list_all_nodes():
    """List all node configurations"""
    nodes = []
    if not os.path.exists(NODES_DIR):
        _clog(f"[CLUSTER] NODES_DIR does not exist: {NODES_DIR}")
        return nodes
    
    _clog(f"[CLUSTER] Listing nodes from {NODES_DIR}")
    try:
        files = os.listdir(NODES_DIR)
        _clog(f"[CLUSTER] Found {len(files)} files in NODES_DIR: {files}")
        
        for filename in files:
            if filename.endswith('.json'):
                node_file = os.path.join(NODES_DIR, filename)
                _clog(f"[CLUSTER] Reading node config: {node_file}")
                try:
                    with open(node_file, 'r') as f:
                        node_data = json.load(f)
                        nodes.append(node_data)
                        _clog(f"[CLUSTER] Loaded node: {node_data.get('hostname', 'unknown')}")
                except Exception as e:
                    _clog(f"[CLUSTER] ERROR reading {node_file}: {e}", error=True)

    except Exception as e:
        _clog(f"[CLUSTER] ERROR listing nodes: {e}", error=True)

    
    _clog(f"[CLUSTER] Total nodes loaded: {len(nodes)}")
    return nodes

def get_local_ip():
    """Get local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_system_resources():
    """Get current system resource usage"""
    mem = psutil.virtual_memory()
    
    # Get container counts (same logic as dashboard - include_compose=False to avoid double counting)
    try:
        from handlers.containers import list_all_containers
        all_containers = list_all_containers(include_compose=False)
        running_containers = 0
        total_containers = len(all_containers)
        
        for container in all_containers:
            if container.status.lower() in ["running", "up"]:
                running_containers += 1
        
        _clog(f"[RESOURCES] Containers: {running_containers}/{total_containers}")
    except Exception as e:
        _clog(f"[RESOURCES] Error counting containers: {e}", error=True)

        import traceback
        traceback.print_exc()
        running_containers = 0
        total_containers = 0
    
    try:
        from handlers.vms import list_vms_with_status
        vms = list_vms_with_status()
        running_vms = sum(1 for vm in vms if vm.status == "running")
        total_vms = len(vms)
        _clog(f"[RESOURCES] VMs: {running_vms}/{total_vms}")
    except Exception as e:
        _clog(f"[RESOURCES] Error counting VMs: {e}", error=True)

        import traceback
        traceback.print_exc()
        running_vms = 0
        total_vms = 0
    
    result = {
        "cpu_usage": psutil.cpu_percent(interval=1),
        "cpu_count": psutil.cpu_count(),
        "memory_usage": mem.percent,
        "memory_total": mem.total,
        "memory_available": mem.available,
        "disk_usage": psutil.disk_usage('/').percent,
        "running_containers": running_containers,
        "total_containers": total_containers,
        "running_vms": running_vms,
        "total_vms": total_vms
    }
    
    _clog(f"[RESOURCES] Returning: containers={total_containers}/{running_containers}, vms={total_vms}/{running_vms}")
    return result

def get_hostname():
    """Get system hostname"""
    return socket.gethostname()

def is_master_node():
    """Check if this node is a master"""
    return os.path.exists(MASTER_CONFIG_FILE)

def is_child_node():
    """Check if this node is a child"""
    return os.path.exists(CHILD_CONFIG_FILE)

def get_cluster_key():
    """Get the cluster key if this node is part of a cluster"""
    if is_child_node():
        child_config = read_child_config()
        if child_config:
            # Try cluster_key first (new format), fall back to key (old format)
            return child_config.get("cluster_key") or child_config.get("key")
    return None


async def _resolve_peer_tls(
    peer: dict,
    cluster_key: str,
    *,
    expected_node_id: str | None = None,
) -> tuple[str, int, str]:
    """Return a pinned peer CA, secure port, and authenticated node identity."""

    is_master_peer = bool(peer.get("master_ip"))
    host = peer.get("master_ip") if is_master_peer else peer.get("ip_address")
    if not host:
        raise ClusterSecurityError("Cluster peer has no address", 503)
    port = normalize_cluster_port(
        peer.get("master_port") if is_master_peer else peer.get("port")
    )
    ca_certificate = (
        peer.get("master_tls_ca") if is_master_peer else peer.get("tls_ca_certificate")
    )
    peer_node_id = expected_node_id or peer.get("hostname") or peer.get("master_hostname")
    if not ca_certificate:
        ca_certificate, authenticated_node_id, port = await bootstrap_peer_ca(
            host,
            port,
            cluster_key,
            expected_node_id=peer_node_id,
        )
        peer_node_id = authenticated_node_id
        if peer.get("master_ip"):
            peer["master_tls_ca"] = ca_certificate
            peer["master_hostname"] = peer_node_id
            peer["master_port"] = port
            write_child_config(peer)
        else:
            peer["tls_ca_certificate"] = ca_certificate
            peer["port"] = port
            write_node_config(str(peer.get("hostname") or peer_node_id), peer)
    return ca_certificate, port, str(peer_node_id or "")


@router.post("/cluster/bootstrap")
async def bootstrap_cluster_transport(request: Request):
    """Return this node's CA with proof bound to the signed request nonce."""

    keyring = load_cluster_keyring()
    key_id = request.state.cluster_key_id
    key = keyring.get(key_id)
    if not key:
        raise HTTPException(status_code=401, detail="Unknown cluster key")
    request_nonce = request.headers.get(HEADER_NONCE, "")
    return create_bootstrap_response(key, request_nonce)

def clear_child_cluster_config() -> bool:
    """Remove local child cluster configuration if present."""
    if os.path.exists(CHILD_CONFIG_FILE):
        os.remove(CHILD_CONFIG_FILE)
        return True
    return False

async def fetch_node_metrics(node: dict, cluster_key: str):
    """Fetch metrics from a child node"""
    ip_address = node.get("ip_address")
    try:
        ca_certificate, port, _ = await _resolve_peer_tls(
            node,
            cluster_key,
            expected_node_id=node.get("hostname"),
        )
        url = cluster_url(ip_address, port, "/cluster/node/metrics")
        _clog(f"[CLUSTER] Fetching metrics from {url}")
        response = await signed_cluster_request(
            "GET",
            url,
            key=cluster_key,
            ca_certificate=ca_certificate,
            timeout=5.0,
        )
            
        if response.status_code == 200:
            metrics = response.json()
            _clog(f"[CLUSTER] Successfully fetched metrics from {ip_address}")
            _clog(f"[CLUSTER] Successfully fetched metrics from {ip_address}")
                
            # Support both formats: new format with cpu.count OR old format with cpu.cores
            cpu_count = metrics.get("cpu", {}).get("count", 0)
            if cpu_count == 0:
                cpu_count = metrics.get("cpu", {}).get("cores", 0)

            # Support both formats: memory.total in bytes OR memory.total in GB
            memory_total = metrics.get("memory", {}).get("total", 0)
            if isinstance(memory_total, float) and memory_total < 1000:
                memory_total = int(memory_total * (1024**3))

            memory_available = metrics.get("memory", {}).get("available", 0)
            if memory_available == 0:
                memory_used = metrics.get("memory", {}).get("used", 0)
                if isinstance(memory_used, float) and memory_used < 1000:
                    memory_used = int(memory_used * (1024**3))
                memory_available = memory_total - memory_used

            containers = metrics.get("containers", {})
            running_containers = containers.get("running", 0)
            total_containers = containers.get("total", 0)

            vms = metrics.get("vms", {})
            running_vms = vms.get("running", 0)
            total_vms = vms.get("total", 0)

            extracted = {
                "cpu_usage": metrics.get("cpu", {}).get("usage", 0),
                "cpu_count": cpu_count,
                "memory_usage": metrics.get("memory", {}).get("usage", 0),
                "memory_total": memory_total,
                "memory_available": memory_available,
                "disk_usage": metrics.get("storage", {}).get("usage", 0),
                "running_containers": running_containers,
                "total_containers": total_containers,
                "running_vms": running_vms,
                "total_vms": total_vms,
                "success": True,
            }
            _clog(
                f"[CLUSTER] Extracted values: cpu_count={extracted['cpu_count']}, "
                f"memory_total={extracted['memory_total']}"
            )
            return extracted
        else:
            _clog(
                f"[CLUSTER] Failed to fetch metrics from {ip_address}: "
                f"HTTP {response.status_code}",
                error=True,
            )

    except (httpx.RequestError, httpx.TimeoutException, Exception) as e:
        _clog(f"[CLUSTER] Error fetching metrics from {ip_address}: {e}", error=True)

    
    return {
        "cpu_usage": 0,
        "cpu_count": 0,
        "memory_usage": 0,
        "memory_total": 0,
        "memory_available": 0,
        "disk_usage": 0,
        "running_containers": 0,
        "total_containers": 0,
        "running_vms": 0,
        "total_vms": 0,
        "success": False
    }

@router.get("/cluster/node/metrics")
async def get_node_metrics():
    """Get current node metrics (for cluster communication)"""
    # Get container counts (same logic as dashboard - include_compose=False to avoid double counting)
    try:
        from handlers.containers import list_all_containers
        all_containers = list_all_containers(include_compose=False)
        running_containers = 0
        total_containers = len(all_containers)
        
        for container in all_containers:
            if container.status.lower() in ["running", "up"]:
                running_containers += 1
        
        _clog(f"[METRICS] Containers: {running_containers}/{total_containers}")
    except Exception as e:
        _clog(f"[METRICS] Error counting containers: {e}", error=True)

        import traceback
        traceback.print_exc()
        running_containers = 0
        total_containers = 0
    
    # Get VM counts
    try:
        from handlers.vms import list_vms_with_status
        vms = list_vms_with_status()
        running_vms = sum(1 for vm in vms if vm.status == "running")
        total_vms = len(vms)
        _clog(f"[METRICS] VMs: {running_vms}/{total_vms}")
    except Exception as e:
        _clog(f"[METRICS] Error counting VMs: {e}", error=True)

        import traceback
        traceback.print_exc()
        running_vms = 0
        total_vms = 0
    
    result = {
        "hostname": get_hostname(),
        "cpu": {
            "usage": psutil.cpu_percent(interval=1),
            "count": psutil.cpu_count()
        },
        "memory": {
            "usage": psutil.virtual_memory().percent,
            "total": psutil.virtual_memory().total,
            "available": psutil.virtual_memory().available
        },
        "storage": {
            "usage": psutil.disk_usage('/').percent,
            "total": psutil.disk_usage('/').total,
            "free": psutil.disk_usage('/').free
        },
        "containers": {
            "running": running_containers,
            "total": total_containers
        },
        "vms": {
            "running": running_vms,
            "total": total_vms
        },
        "timestamp": datetime.now().isoformat()
    }
    
    _clog(f"[METRICS] Returning metrics with containers={total_containers}/{running_containers}, vms={total_vms}/{running_vms}")
    return result

@router.get("/cluster/debug")
async def get_cluster_debug():
    """Debug information for cluster troubleshooting"""
    import os
    
    debug_info = {
        "is_master": is_master_node(),
        "is_child": is_child_node(),
        "hostname": get_hostname(),
        "local_ip": get_local_ip(),
        "master_config_exists": os.path.exists(MASTER_CONFIG_FILE),
        "child_config_exists": os.path.exists(CHILD_CONFIG_FILE),
        "nodes_dir_exists": os.path.exists(NODES_DIR),
        "nodes_dir_path": NODES_DIR,
        "nodes_dir_writable": os.access(NODES_DIR, os.W_OK) if os.path.exists(NODES_DIR) else False,
        "node_files": [],
        "master_config": None,
        "child_config": None
    }
    
    if os.path.exists(NODES_DIR):
        debug_info["node_files"] = os.listdir(NODES_DIR)
        debug_info["node_configs"] = {}
        for filename in os.listdir(NODES_DIR):
            if filename.endswith('.json'):
                hostname = filename[:-5]  # Remove .json
                node_config = read_node_config(hostname)
                if node_config:
                    debug_info["node_configs"][hostname] = node_config
    
    if is_master_node():
        debug_info["master_config"] = _redact_cluster_secrets(read_master_config())
        debug_info["stored_nodes"] = list_all_nodes()
    
    if is_child_node():
        debug_info["child_config"] = _redact_cluster_secrets(read_child_config())
    
    return debug_info

@router.post("/cluster/test-write")
async def test_write_permissions():
    """Test if we can write to the nodes directory"""
    ensure_config_dir()
    
    test_file = os.path.join(NODES_DIR, "test_write.json")
    test_data = {"test": "data", "timestamp": datetime.now().isoformat()}
    
    try:
        write_cluster_json(test_file, test_data)
        
        with open(test_file, 'r') as f:
            read_data = json.load(f)
        
        os.remove(test_file)
        
        return {
            "success": True,
            "message": "Write test successful",
            "data_written": test_data,
            "data_read": read_data
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "nodes_dir": NODES_DIR,
            "nodes_dir_exists": os.path.exists(NODES_DIR),
            "nodes_dir_writable": os.access(NODES_DIR, os.W_OK) if os.path.exists(NODES_DIR) else False
        }

@router.get("/cluster/info")
async def get_cluster_info():
    """Get cluster information"""
    is_master = is_master_node()
    is_child = is_child_node()
    is_member = is_master or is_child
    
    nodes = []
    master_ip = None
    
    if is_master:
        master_config = read_master_config()
        cluster_key = master_config.get("key")
        master_ip = get_local_ip()
        
        master_resources = get_system_resources()

        master_node = {
            "id": get_hostname(),
            "hostname": get_hostname(),
            "ip_address": get_local_ip(),
            "port": CLUSTER_TLS_PORT,
            "status": "online",
            "role": "master",
            "resources": master_resources,
            "last_seen": datetime.now().isoformat()
        }
        nodes.append(master_node)
        
        _clog(f"[CLUSTER] Master node added with containers: {master_resources.get('total_containers')}/{master_resources.get('running_containers')}, vms: {master_resources.get('total_vms')}/{master_resources.get('running_vms')}")
        
        child_nodes = list_all_nodes()
        _clog(f"[CLUSTER] Master node found {len(child_nodes)} nodes in directory")
        for node in child_nodes:
            _clog(f"[CLUSTER] Processing node: {node.get('hostname')}")
            if node.get("hostname") != get_hostname():
                resources = await fetch_node_metrics(node, cluster_key)
                
                node["resources"] = resources
                node["last_seen"] = datetime.now().isoformat()
                
                is_online = resources.pop("success", False)
                
                nodes.append({
                    "id": node.get("hostname"),
                    "hostname": node.get("hostname"),
                    "ip_address": node.get("ip_address"),
                    "port": normalize_cluster_port(node.get("port")),
                    "status": "online" if is_online else "offline",
                    "role": "child",
                    "resources": resources,
                    "last_seen": node.get("last_seen", "")
                })
    
    elif is_child:
        child_config = read_child_config()
        master_ip = child_config.get("master_ip")
        master_port = normalize_cluster_port(child_config.get("master_port"))
        cluster_key = child_config.get("cluster_key") or child_config.get("key")
        
        _clog(f"[CLUSTER] Child node trying to fetch full cluster info from {master_ip}:{master_port}")
        
        try:
            master_ca, master_port, _ = await _resolve_peer_tls(
                child_config,
                cluster_key,
                expected_node_id=child_config.get("master_hostname"),
            )
            write_child_config(child_config)
            response = await signed_cluster_request(
                "GET",
                cluster_url(master_ip, master_port, "/cluster/info"),
                key=cluster_key,
                ca_certificate=master_ca,
                timeout=5.0,
            )
            if response.status_code == 200:
                master_view = response.json()
                _clog(f"[CLUSTER] Successfully fetched full cluster info from master")
                nodes = master_view.get("nodes", [])
            else:
                _clog(f"[CLUSTER] Failed to fetch full cluster info: HTTP {response.status_code}", error=True)
                raise Exception("Master unreachable")
        except Exception as e:
            _clog(f"[CLUSTER] Master unreachable while fetching full cluster info: {e}")
            nodes.append({
                "id": "master",
                "hostname": "master",
                "ip_address": master_ip,
                "port": master_port,
                "status": "offline",
                "role": "master",
                "resources": {
                    "cpu_usage": 0,
                    "cpu_count": 0,
                    "memory_usage": 0,
                    "memory_total": 0,
                    "memory_available": 0,
                    "disk_usage": 0,
                    "running_containers": 0,
                    "total_containers": 0,
                    "running_vms": 0,
                    "total_vms": 0
                },
                "last_seen": ""
            })

            child_node = {
                "id": get_hostname(),
                "hostname": get_hostname(),
                "ip_address": get_local_ip(),
                "port": CLUSTER_TLS_PORT,
                "status": "online",
                "role": "child",
                "resources": get_system_resources(),
                "last_seen": datetime.now().isoformat()
            }
            nodes.append(child_node)
    
    return ClusterInfo(
        is_master=is_master,
        is_member=is_member,
        master_ip=master_ip,
        nodes=nodes
    )

@router.post("/cluster/create")
async def create_cluster(request: ClusterCreateRequest):
    """Create a new cluster and become master node"""
    if is_master_node():
        raise HTTPException(status_code=400, detail="This node is already a master")
    
    if is_child_node():
        raise HTTPException(status_code=400, detail="This node is already a child. Leave the cluster first")
    
    ensure_node_tls()
    cluster_key = secrets.token_urlsafe(48)
    cluster_key_id = derive_key_id(cluster_key)
    
    master_config = {
        "key": cluster_key,
        "key_id": cluster_key_id,
        "previous_keys": [],
        "cluster_name": request.cluster_name,
        "created_at": datetime.now().isoformat()
    }
    
    write_master_config(master_config)
    
    master_node_config = {
        "hostname": get_hostname(),
        "ip_address": get_local_ip(),
        "port": CLUSTER_TLS_PORT,
        "tls_ca_certificate": ensure_node_tls().ca_certificate,
        "resources": get_system_resources(),
        "last_seen": datetime.now().isoformat()
    }
    
    write_node_config(get_hostname(), master_node_config)
    
    return {
        "message": "Cluster created successfully",
        "token": cluster_key,
        "key_id": cluster_key_id,
        "master_ip": get_local_ip(),
        "cluster_port": CLUSTER_TLS_PORT,
    }

@router.post("/cluster/join")
async def join_cluster(request: ClusterJoinRequest):
    """Join an existing cluster as child node"""
    _clog(f"[CLUSTER] ========================================")
    _clog(f"[CLUSTER] JOIN REQUEST INITIATED")
    _clog(f"[CLUSTER] Target Master: {request.master_ip}:{request.port}")
    
    if is_master_node():
        _clog(f"[CLUSTER] ERROR: This node is already a master", error=True)

        raise HTTPException(status_code=400, detail="This node is already a master")
    
    if is_child_node():
        _clog(f"[CLUSTER] ERROR: Already part of a cluster", error=True)

        raise HTTPException(status_code=400, detail="Already part of a cluster")
    
    my_hostname = get_hostname()
    my_ip = get_local_ip()
    local_tls = ensure_node_tls()
    secure_master_port = normalize_cluster_port(request.port)
    
    _clog(f"[CLUSTER] My hostname: {my_hostname}")
    _clog(f"[CLUSTER] My IP: {my_ip}")
    
    my_resources = get_system_resources()
    node_data = {
        "hostname": my_hostname,
        "ip_address": my_ip,
        "port": CLUSTER_TLS_PORT,
        "tls_ca_certificate": local_tls.ca_certificate,
        "resources": my_resources,
    }
    
    _clog(f"[CLUSTER] Attempting registration with master...")
    
    try:
        master_ca, master_hostname, secure_master_port = await bootstrap_peer_ca(
            request.master_ip,
            secure_master_port,
            request.token,
            node_id=my_hostname,
        )
        master_url = cluster_url(
            request.master_ip,
            secure_master_port,
            "/cluster/register",
        )
        _clog(f"[CLUSTER] POST {master_url}")

        response = await signed_cluster_request(
            "POST",
            master_url,
            key=request.token,
            node_id=my_hostname,
            ca_certificate=master_ca,
            json_data=node_data,
            timeout=10.0,
        )

        _clog(f"[CLUSTER] Response status: {response.status_code}")

        if response.status_code != 200:
            try:
                error_detail = response.json().get(
                    "detail",
                    "Failed to register with master",
                )
            except ValueError:
                error_detail = response.text
            _clog(f"[CLUSTER] Registration FAILED: {error_detail}", error=True)
            raise HTTPException(
                status_code=400,
                detail=f"Master rejected registration: {error_detail}",
            )

        response_data = response.json()
        assigned_hostname = response_data.get("hostname", my_hostname)
        master_hostname = response_data.get("master_hostname", master_hostname)

        _clog(f"[CLUSTER] Registration SUCCESSFUL")
        _clog(f"[CLUSTER] Assigned hostname: {assigned_hostname}")
            
    except HTTPException:
        raise
    except httpx.RequestError as e:
        _clog(f"[CLUSTER] Connection error: {type(e).__name__}: {str(e)}", error=True)

        raise HTTPException(status_code=400, detail=f"Failed to connect to master: {str(e)}")
    except httpx.TimeoutException:
        _clog(f"[CLUSTER] Connection timeout to {request.master_ip}:{request.port}")
        raise HTTPException(status_code=400, detail="Connection to master timed out")
    except ClusterSecurityError as e:
        _clog(f"[CLUSTER] Secure transport error: {e}", error=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        _clog(f"[CLUSTER] Unexpected error: {type(e).__name__}: {str(e)}", error=True)

        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error during registration: {str(e)}")
    
    child_config = {
        "cluster_key": request.token,  # Store as cluster_key for consistency
        "key": request.token,  # Keep backwards compatibility
        "cluster_key_id": derive_key_id(request.token),
        "previous_keys": [],
        "master_ip": request.master_ip,
        "master_port": secure_master_port,
        "master_hostname": master_hostname,
        "master_tls_ca": master_ca,
        "tls_ca_certificate": local_tls.ca_certificate,
        "joined_at": datetime.now().isoformat(),
        "assigned_hostname": assigned_hostname,
    }
    
    _clog(f"[CLUSTER] Writing child configuration...")
    write_child_config(child_config)
    _clog(f"[CLUSTER] Child configuration written to {CHILD_CONFIG_FILE}")

    # Pull HA config from master so this node is in sync
    try:
        ha_resp = await signed_cluster_request(
            "GET",
            cluster_url(
                request.master_ip,
                secure_master_port,
                "/cluster/ha/config",
            ),
            key=request.token,
            node_id=assigned_hostname,
            ca_certificate=master_ca,
            timeout=5.0,
        )
        if ha_resp.status_code == 200:
            from lib.ha_manager import get_ha_manager
            get_ha_manager().apply_synced_config(ha_resp.json())
            _clog(f"[CLUSTER] HA config pulled from master and applied")
    except Exception as e:
        _clog(f"[CLUSTER] Could not pull HA config from master (non-fatal): {e}")

    _clog(f"[CLUSTER] JOIN COMPLETED SUCCESSFULLY")
    _clog(f"[CLUSTER] ========================================")

    return {
        "message": "Successfully joined cluster",
        "master_ip": request.master_ip,
        "master_port": secure_master_port,
        "assigned_hostname": assigned_hostname,
    }

@router.post("/cluster/register")
async def register_node(payload: NodeRegistrationRequest, request: Request):
    """Register a child node with the master (master only)"""
    _clog(f"[CLUSTER] ========================================")
    _clog(
        f"[CLUSTER] Registration request from {payload.hostname} "
        f"({payload.ip_address}:{payload.port})"
    )
    
    if not is_master_node():
        _clog(f"[CLUSTER] ERROR: This node is not a master", error=True)

        raise HTTPException(status_code=403, detail="Only master node can register nodes")
    
    _clog(f"[CLUSTER] This is a master node, proceeding...")
    
    master_config = read_master_config()
    if not master_config:
        _clog(f"[CLUSTER] ERROR: Master config not found", error=True)

        raise HTTPException(status_code=500, detail="Master configuration not found")
    
    signed_node = request.state.cluster_node
    if signed_node != payload.hostname:
        raise HTTPException(
            status_code=401,
            detail="Signed node identity does not match registration payload",
        )
    try:
        payload.ip_address = str(ipaddress.ip_address(payload.ip_address))
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid node IP address") from error
    try:
        ssl.create_default_context(cadata=payload.tls_ca_certificate)
    except ssl.SSLError as error:
        raise HTTPException(status_code=400, detail="Invalid node CA certificate") from error

    _clog(f"[CLUSTER] Signed registration verified for {signed_node}")
    
    original_hostname = payload.hostname
    all_nodes = list_all_nodes()
    
    same_ip_node = None
    for node in all_nodes:
        if node.get("ip_address") == payload.ip_address:
            same_ip_node = node
            break
    
    if same_ip_node:
        existing_hostname = same_ip_node.get("hostname")
        _clog(f"[CLUSTER] Node with IP {payload.ip_address} already exists as {existing_hostname}, updating...")
        same_ip_node["hostname"] = existing_hostname  # Keep the original hostname
        same_ip_node["ip_address"] = payload.ip_address
        same_ip_node["port"] = normalize_cluster_port(payload.port)
        same_ip_node["tls_ca_certificate"] = payload.tls_ca_certificate
        same_ip_node["resources"] = payload.resources
        same_ip_node["last_seen"] = datetime.now().isoformat()
        try:
            write_node_config(existing_hostname, same_ip_node)
            _clog(f"[CLUSTER] Node {existing_hostname} updated successfully")
            return {
                "message": "Node updated successfully",
                "hostname": existing_hostname,
                "master_hostname": get_hostname(),
            }
        except Exception as e:
            _clog(f"[CLUSTER] ERROR updating node: {e}", error=True)

            raise HTTPException(status_code=500, detail=f"Failed to update node: {str(e)}")
    
    unique_hostname = find_unique_hostname(original_hostname)
    
    if unique_hostname != original_hostname:
        _clog(f"[CLUSTER] Hostname {original_hostname} already exists, using {unique_hostname} instead")
    
    _clog(f"[CLUSTER] Creating new node config for {unique_hostname}")
    node_config = {
        "hostname": unique_hostname,
        "original_hostname": original_hostname,
        "ip_address": payload.ip_address,
        "port": normalize_cluster_port(payload.port),
        "tls_ca_certificate": payload.tls_ca_certificate,
        "resources": payload.resources,
        "last_seen": datetime.now().isoformat(),
        "registered_at": datetime.now().isoformat()
    }
    
    _clog(f"[CLUSTER] Node config: {node_config}")
    
    try:
        write_node_config(unique_hostname, node_config)
        _clog(f"[CLUSTER] Node {unique_hostname} registered successfully")
        _clog(f"[CLUSTER] ========================================")
        
        verification = read_node_config(unique_hostname)
        if verification:
            _clog(f"[CLUSTER] Verification: Node config readable after write")
        else:
            _clog(f"[CLUSTER] WARNING: Node config not readable after write!")
        
        return {
            "message": "Node registered successfully",
            "hostname": unique_hostname,
            "original_hostname": original_hostname if unique_hostname != original_hostname else None,
            "master_hostname": get_hostname(),
        }
    except Exception as e:
        _clog(f"[CLUSTER] ERROR registering node: {e}", error=True)

        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to register node: {str(e)}")


@router.post("/cluster/keys/update")
async def update_cluster_key(payload: ClusterKeyUpdateRequest):
    """Install a key distributed by the master over a signed, pinned channel."""

    if not is_child_node():
        raise HTTPException(status_code=403, detail="Only child nodes accept key updates")
    if derive_key_id(payload.key) != payload.key_id:
        raise HTTPException(status_code=400, detail="Cluster key identifier mismatch")
    if payload.previous_valid_until <= int(time.time()):
        raise HTTPException(status_code=400, detail="Key overlap window has expired")
    try:
        install_rotated_child_key(
            payload.key,
            payload.key_id,
            payload.previous_valid_until,
        )
    except ClusterSecurityError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return {"updated": True, "key_id": payload.key_id}


@router.post("/cluster/keys/rotate")
async def rotate_cluster_key(payload: ClusterKeyRotationRequest):
    """Rotate the cluster key with an overlap window and peer acknowledgement."""

    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only the master can rotate keys")
    config = read_master_config()
    if not config or not config.get("key"):
        raise HTTPException(status_code=503, detail="Master cluster key is unavailable")

    now = int(time.time())
    old_key = config["key"]
    old_key_id = config.get("key_id") or derive_key_id(old_key)
    pending = config.get("pending_key")
    if not isinstance(pending, dict) or not pending.get("key"):
        new_key = secrets.token_urlsafe(48)
        pending = {
            "key": new_key,
            "key_id": derive_key_id(new_key),
            "created_at": now,
        }
        config["pending_key"] = pending
        write_master_config(config)

    new_key = pending["key"]
    new_key_id = pending.get("key_id") or derive_key_id(new_key)
    previous_valid_until = now + payload.overlap_seconds
    update_payload = {
        "key": new_key,
        "key_id": new_key_id,
        "previous_valid_until": previous_valid_until,
    }

    updated_nodes = []
    failures = []
    for node in list_all_nodes():
        node_name = node.get("hostname")
        if node_name == get_hostname():
            continue
        try:
            ca_certificate, port, _ = await _resolve_peer_tls(
                node,
                old_key,
                expected_node_id=node_name,
            )
            response = await signed_cluster_request(
                "POST",
                cluster_url(node.get("ip_address"), port, "/cluster/keys/update"),
                key=old_key,
                key_id=old_key_id,
                ca_certificate=ca_certificate,
                json_data=update_payload,
                timeout=10.0,
            )
            if response.status_code != 200:
                raise ClusterSecurityError(
                    f"HTTP {response.status_code} from key update",
                    503,
                )
            updated_nodes.append(node_name)
        except Exception as error:
            failures.append({"node": node_name, "error": str(error)})

    if failures:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Key rotation is pending; retry after peers recover",
                "key_id": new_key_id,
                "updated_nodes": updated_nodes,
                "failures": failures,
            },
        )

    previous_keys = []
    for entry in config.get("previous_keys", []):
        if not isinstance(entry, dict) or entry.get("key_id") == old_key_id:
            continue
        try:
            if int(entry.get("valid_until", 0)) > now:
                previous_keys.append(entry)
        except (TypeError, ValueError):
            continue
    previous_keys.append(
        {
            "key": old_key,
            "key_id": old_key_id,
            "valid_until": previous_valid_until,
        }
    )
    config["key"] = new_key
    config["key_id"] = new_key_id
    config["previous_keys"] = previous_keys
    config.pop("pending_key", None)
    config["rotated_at"] = datetime.now().isoformat()
    write_master_config(config)

    return {
        "message": "Cluster key rotated successfully",
        "key_id": new_key_id,
        "token": new_key,
        "previous_valid_until": previous_valid_until,
        "updated_nodes": updated_nodes,
    }

@router.post("/cluster/leave")
async def leave_cluster():
    """Leave the current cluster"""
    if not is_master_node() and not is_child_node():
        raise HTTPException(status_code=400, detail="Not part of any cluster")
    
    if is_master_node():
        master_config = read_master_config()
        cluster_key = master_config.get("key") if master_config else None
        child_nodes = [
            node for node in list_all_nodes()
            if node.get("hostname") != get_hostname()
        ]

        if cluster_key and child_nodes:
            _clog(f"[CLUSTER] Notifying {len(child_nodes)} child node(s) about master leave")
            try:
                for node in child_nodes:
                    node_ip = node.get("ip_address")
                    if not node_ip:
                        _clog(f"[CLUSTER] Skipping child node without IP: {node.get('hostname', 'unknown')}", error=True)
                        continue

                    try:
                        ca_certificate, node_port, _ = await _resolve_peer_tls(
                            node,
                            cluster_key,
                            expected_node_id=node.get("hostname"),
                        )
                        response = await signed_cluster_request(
                            "POST",
                            cluster_url(node_ip, node_port, "/cluster/leave"),
                            key=cluster_key,
                            ca_certificate=ca_certificate,
                            timeout=10.0,
                        )

                        if response.status_code == 200:
                            _clog(f"[CLUSTER] Child node notified successfully: {node.get('hostname', node_ip)}")
                        else:
                            _clog(
                                f"[CLUSTER] Child node leave notification failed for {node.get('hostname', node_ip)}: HTTP {response.status_code}",
                                error=True,
                            )
                    except Exception as e:
                        _clog(
                            f"[CLUSTER] Error notifying child node {node.get('hostname', node_ip)}: {e}",
                            error=True,
                        )
            except Exception as e:
                _clog(f"[CLUSTER] Error while notifying child nodes: {e}", error=True)

        if os.path.exists(MASTER_CONFIG_FILE):
            os.remove(MASTER_CONFIG_FILE)
        
        if os.path.exists(NODES_DIR):
            for filename in os.listdir(NODES_DIR):
                node_file = os.path.join(NODES_DIR, filename)
                if os.path.isfile(node_file):
                    os.remove(node_file)
        
    elif is_child_node():
        child_config = read_child_config()
        master_ip = None
        master_port = CLUSTER_TLS_PORT
        cluster_key = None
        assigned_hostname = None

        if child_config:
            master_ip = child_config.get("master_ip")
            master_port = normalize_cluster_port(child_config.get("master_port"))
            cluster_key = child_config.get("cluster_key") or child_config.get("key")
            assigned_hostname = child_config.get("assigned_hostname")

        node_id = assigned_hostname or get_hostname()

        if master_ip and cluster_key:
            _clog(f"[CLUSTER] Notifying master about child leave: {node_id} -> {master_ip}:{master_port}")
            try:
                master_ca, master_port, _ = await _resolve_peer_tls(
                    child_config,
                    cluster_key,
                    expected_node_id=child_config.get("master_hostname"),
                )
                response = await signed_cluster_request(
                    "DELETE",
                    cluster_url(master_ip, master_port, f"/cluster/nodes/{node_id}"),
                    key=cluster_key,
                    ca_certificate=master_ca,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    _clog(f"[CLUSTER] Master notified successfully for child node: {node_id}")
                else:
                    _clog(
                        f"[CLUSTER] Master notification failed for child node {node_id}: HTTP {response.status_code}",
                        error=True,
                    )
            except Exception as e:
                _clog(f"[CLUSTER] Error notifying master about child leave: {e}", error=True)

        clear_child_cluster_config()
    
    return {"message": "Successfully left cluster"}

@router.post("/cluster/force-leave")
async def force_leave_cluster():
    """Force a child node to leave the cluster without notifying the master again."""
    if not is_child_node():
        raise HTTPException(status_code=400, detail="This node is not a child node")

    child_config = read_child_config() or {}
    node_id = child_config.get("assigned_hostname") or get_hostname()

    clear_child_cluster_config()
    notify("system_alert", f"Node '{node_id}' was removed from the cluster by the master")
    _clog(f"[CLUSTER] Force leave completed for child node: {node_id}")

    return {"message": "Node removed from cluster successfully", "node_id": node_id}

@router.delete("/cluster/nodes/{node_id}")
async def remove_node(node_id: str):
    """Remove a node from the cluster (master only)"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can remove nodes")

    resolved_hostname, node_config = resolve_node_for_removal(node_id)
    if not node_config:
        raise HTTPException(status_code=404, detail="Node not found")

    resolved_hostname = resolved_hostname or node_id
    node_ip = node_config.get("ip_address")
    master_config = read_master_config()
    cluster_key = master_config.get("key") if master_config else None
    
    delete_node_config(resolved_hostname)

    # Clean stale HA heartbeat state for removed node if HA is active.
    try:
        from lib.ha_manager import get_ha_manager
        ha_manager = get_ha_manager()
        with ha_manager._lock:
            if resolved_hostname in ha_manager.heartbeats:
                del ha_manager.heartbeats[resolved_hostname]
                ha_manager._save_heartbeats()
    except Exception as e:
        _clog(f"[CLUSTER] Could not clean HA heartbeat for removed node {resolved_hostname}: {e}", error=True)

    if node_ip and cluster_key:
        asyncio.create_task(
            notify_removed_node(resolved_hostname, node_config, cluster_key)
        )
    else:
        _clog(f"[CLUSTER] Removed node {resolved_hostname} has no reachable address or cluster key", error=True)
    
    return {"message": f"Node {resolved_hostname} removed successfully", "node_id": resolved_hostname}

@router.get("/cluster/nodes")
async def get_cluster_nodes():
    """Get all nodes in the cluster"""
    if not is_master_node() and not is_child_node():
        raise HTTPException(status_code=400, detail="Not part of any cluster")
    
    if is_master_node():
        nodes = list_all_nodes()
        return {"nodes": nodes}
    else:
        # Child nodes don't have access to all node configs
        return {"nodes": []}

# Load Balancing Endpoints

class WorkloadPlacementRequest(BaseModel):
    service_id: str
    strategy: str = "least_loaded"
    required_resources: Optional[dict] = None

class AffinityRuleRequest(BaseModel):
    service_id: str
    node_id: str

@router.post("/cluster/workload/placement")
async def get_workload_placement(request: WorkloadPlacementRequest):
    """Get recommended node for workload placement"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can manage workload placement")
    
    cluster_info = await get_cluster_info()
    nodes = cluster_info.nodes
    
    lb = get_load_balancer()
    
    try:
        strategy = LoadBalancingStrategy(request.strategy)
    except ValueError:
        strategy = LoadBalancingStrategy.LEAST_LOADED
    
    nodes_dict = [
        {
            "id": n.id,
            "hostname": n.hostname,
            "ip_address": n.ip_address,
            "port": n.port,
            "status": n.status,
            "role": n.role,
            "resources": n.resources
        }
        for n in nodes
    ]
    
    selected_node = lb.select_node(
        nodes_dict,
        strategy=strategy,
        service_id=request.service_id,
        required_resources=request.required_resources
    )
    
    if not selected_node:
        raise HTTPException(status_code=404, detail="No suitable node found for workload placement")
    
    return {
        "selected_node": selected_node,
        "strategy": request.strategy,
        "service_id": request.service_id
    }

@router.get("/cluster/load/distribution")
async def get_load_distribution():
    """Get cluster load distribution statistics"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can view load distribution")
    
    cluster_info = await get_cluster_info()
    
    nodes_dict = [
        {
            "id": n.id,
            "hostname": n.hostname,
            "status": n.status,
            "resources": n.resources
        }
        for n in cluster_info.nodes
    ]
    
    lb = get_load_balancer()
    distribution = lb.get_cluster_load_distribution(nodes_dict)
    
    return distribution

@router.get("/cluster/load/recommendations")
async def get_rebalancing_recommendations():
    """Get recommendations for workload rebalancing"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can get rebalancing recommendations")
    
    cluster_info = await get_cluster_info()
    
    nodes_dict = [
        {
            "id": n.id,
            "hostname": n.hostname,
            "status": n.status,
            "resources": n.resources
        }
        for n in cluster_info.nodes
    ]
    
    lb = get_load_balancer()
    recommendations = lb.recommend_rebalancing(nodes_dict)
    
    return {
        "recommendations": recommendations,
        "count": len(recommendations)
    }

@router.post("/cluster/affinity")
async def set_affinity_rule(request: AffinityRuleRequest):
    """Set affinity rule for a service"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can manage affinity rules")
    
    lb = get_load_balancer()
    lb.set_affinity(request.service_id, request.node_id)
    
    return {
        "message": f"Affinity rule set for service {request.service_id} to node {request.node_id}"
    }

@router.delete("/cluster/affinity/{service_id}")
async def remove_affinity_rule(service_id: str):
    """Remove affinity rule for a service"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can manage affinity rules")
    
    lb = get_load_balancer()
    lb.remove_affinity(service_id)
    
    return {
        "message": f"Affinity rule removed for service {service_id}"
    }

# Container Synchronization Endpoints

class SyncRuleRequest(BaseModel):
    service_name: str
    strategy: str = "distribute"
    target_nodes: Optional[List[str]] = None
    replica_count: int = 1

class ContainerMigrationRequest(BaseModel):
    service_name: str
    source_node_id: str
    target_node_id: str

@router.post("/cluster/sync/rules")
async def add_sync_rule(request: SyncRuleRequest):
    """Reject sync configuration while transactional replication is disabled."""
    raise HTTPException(
        status_code=501,
        detail="Container synchronization is disabled until transactional replication is available",
    )

@router.get("/cluster/sync/rules")
async def get_sync_rules():
    """Report that container synchronization is unavailable."""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can view sync rules")
    return {"enabled": False, "rules": {}}

@router.delete("/cluster/sync/rules/{service_name}")
async def remove_sync_rule(service_name: str):
    """Reject sync configuration while transactional replication is disabled."""
    raise HTTPException(
        status_code=501,
        detail="Container synchronization is disabled until transactional replication is available",
    )

@router.post("/cluster/sync/execute")
async def execute_synchronization():
    """Never report success while transactional replication is disabled."""
    raise HTTPException(
        status_code=501,
        detail="Container synchronization is disabled; no replication was attempted",
    )

@router.get("/cluster/sync/status")
async def get_sync_status():
    """Report disabled status instead of stale synchronization state."""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can view sync status")
    return {
        "enabled": False,
        "status": "disabled",
        "distribution": {},
    }

@router.post("/cluster/sync/migrate")
async def migrate_container(request: ContainerMigrationRequest):
    """Reject migration until source stop and rollback are transactional."""
    raise HTTPException(
        status_code=501,
        detail="Container migration is disabled until source stop and rollback are transactional",
    )

@router.get("/cluster/containers/distribution")
async def get_container_distribution():
    """Get distribution of containers across cluster nodes"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can view container distribution")
    
    sync_manager = get_sync_manager()
    distribution = sync_manager.get_container_distribution()
    
    return {
        "distribution": distribution,
        "node_count": len(distribution)
    }

# Enhanced Metrics and Monitoring Endpoints

@router.get("/cluster/metrics/detailed")
async def get_detailed_metrics():
    """Get detailed system metrics for this node"""
    metrics_collector = get_metrics_collector()
    node_id = get_hostname()
    
    metrics = metrics_collector.collect_system_metrics(node_id)
    
    return {
        "node_id": node_id,
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics
    }

@router.get("/cluster/metrics/history")
async def get_metrics_history(node_id: str, metric_name: str, minutes: int = 60):
    """Get historical metrics data"""
    if not is_master_node() and node_id != get_hostname():
        raise HTTPException(status_code=403, detail="Can only view own metrics")
    
    metrics_collector = get_metrics_collector()
    history = metrics_collector.get_metric_history(node_id, metric_name, minutes)
    
    return {
        "node_id": node_id,
        "metric_name": metric_name,
        "history": history,
        "data_points": len(history)
    }

@router.get("/cluster/metrics/summary")
async def get_cluster_metrics_summary():
    """Get comprehensive cluster metrics summary"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can view cluster metrics summary")
    
    cluster_info = await get_cluster_info()
    
    nodes_dict = [
        {
            "id": n.id,
            "status": n.status,
            "resources": n.resources
        }
        for n in cluster_info.nodes
    ]
    
    metrics_collector = get_metrics_collector()
    summary = metrics_collector.get_cluster_metrics_summary(nodes_dict)
    
    return summary

@router.get("/cluster/alerts")
async def get_alerts(level: Optional[str] = None):
    """Get active alerts"""
    metrics_collector = get_metrics_collector()
    alerts = metrics_collector.get_active_alerts(level)
    
    return {
        "alerts": alerts,
        "count": len(alerts)
    }

@router.post("/cluster/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert"""
    metrics_collector = get_metrics_collector()
    success = metrics_collector.acknowledge_alert(alert_id)
    
    if success:
        return {"message": f"Alert {alert_id} acknowledged"}
    else:
        raise HTTPException(status_code=404, detail="Alert not found")

@router.delete("/cluster/alerts/cleanup")
async def cleanup_old_alerts(hours: int = 24):
    """Clean up old alerts"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can cleanup alerts")
    
    metrics_collector = get_metrics_collector()
    metrics_collector.clear_old_alerts(hours)
    
    return {"message": f"Alerts older than {hours} hours cleared"}

@router.get("/cluster/health")
async def get_cluster_health():
    """Get overall cluster health status"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can view cluster health")
    
    cluster_info = await get_cluster_info()
    
    nodes_dict = [
        {
            "id": n.id,
            "hostname": n.hostname,
            "status": n.status,
            "resources": n.resources
        }
        for n in cluster_info.nodes
    ]
    
    total_nodes = len(nodes_dict)
    online_nodes = sum(1 for n in nodes_dict if n["status"] == "online")
    offline_nodes = total_nodes - online_nodes
    
    lb = get_load_balancer()
    load_distribution = lb.get_cluster_load_distribution(nodes_dict)
    
    metrics_collector = get_metrics_collector()
    alerts = metrics_collector.get_active_alerts()
    critical_alerts = [a for a in alerts if a.get("level") == "critical"]
    warning_alerts = [a for a in alerts if a.get("level") == "warning"]
    
    total_cpu_cores = 0
    total_memory_gb = 0.0
    
    _clog(f"[CLUSTER] ========== HEALTH CALCULATION ==========")
    _clog(f"[CLUSTER] Total nodes: {len(nodes_dict)}")
    
    for node in nodes_dict:
        resources = node.get("resources", {})
        node_cores = resources.get("cpu_count", 0)
        node_memory_bytes = resources.get("memory_total", 0)
        node_memory_gb = node_memory_bytes / (1024**3)
        
        _clog(f"[CLUSTER] Node: {node.get('hostname')}")
        _clog(f"[CLUSTER]   - Status: {node.get('status')}")
        _clog(f"[CLUSTER]   - CPU Cores: {node_cores}")
        _clog(f"[CLUSTER]   - Memory: {node_memory_gb:.2f} GB")
        _clog(f"[CLUSTER]   - Resources: {resources}")
        
        total_cpu_cores += node_cores
        total_memory_gb += node_memory_gb
    
    _clog(f"[CLUSTER] TOTALS:")
    _clog(f"[CLUSTER]   - Total CPU Cores: {total_cpu_cores}")
    _clog(f"[CLUSTER]   - Total Memory: {total_memory_gb:.2f} GB")
    _clog(f"[CLUSTER] ==========================================")

    health_status = "healthy"
    if offline_nodes > 0 or len(critical_alerts) > 0:
        health_status = "critical"
    elif len(warning_alerts) > 0 or load_distribution["average_cpu"] > 80:
        health_status = "warning"
    
    return {
        "status": health_status,
        "nodes": {
            "total": total_nodes,
            "online": online_nodes,
            "offline": offline_nodes
        },
        "load": {
            "average_cpu": load_distribution["average_cpu"],
            "average_memory": load_distribution["average_memory"],
            "average_disk": load_distribution["average_disk"],
            "total_capacity": load_distribution["total_capacity"],
            "total_cpu_cores": total_cpu_cores,
            "total_memory_gb": round(total_memory_gb, 2)
        },
        "alerts": {
            "total": len(alerts),
            "critical": len(critical_alerts),
            "warning": len(warning_alerts)
        },
        "timestamp": datetime.now().isoformat()
    }

# Replication configuration directory
REPLICATIONS_FILE = os.path.join(UPSERVX_CONFIG_DIR, "replications.json")
REPLICATIONS_LOCK = InterProcessFileLock(f"{REPLICATIONS_FILE}.lock")

class ReplicationCreate(BaseModel):
    origin_node: str
    destination_node: str
    name: str
    type: str
    sync_schedule: str

def read_replications():
    """Read replication rules from config file"""
    with REPLICATIONS_LOCK:
        data = secure_read_json(REPLICATIONS_FILE, missing=[])
        if not isinstance(data, list):
            raise RuntimeError("Replication configuration must be a JSON list")
        return data

def write_replications(replications: list):
    """Write replication rules to config file"""
    ensure_config_dir()
    try:
        with REPLICATIONS_LOCK:
            write_cluster_json(REPLICATIONS_FILE, replications)
        _clog(f"[REPLICATION] Saved {len(replications)} replication rules")
    except Exception as e:
        _clog(f"[REPLICATION] Error writing replications: {e}", error=True)

        raise

@router.get("/cluster/replications")
async def get_replications():
    """Get all replication rules"""
    if not is_master_node() and not is_child_node():
        return []
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can manage replications")
    
    replications = read_replications()
    return replications

@router.post("/cluster/replications")
async def create_replication(replication: ReplicationCreate):
    """Create a new replication rule"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can manage replications")
    
    with REPLICATIONS_LOCK:
        replications = read_replications()
        import uuid
        new_replication = {
            "id": str(uuid.uuid4()),
            "origin_node": replication.origin_node,
            "destination_node": replication.destination_node,
            "name": replication.name,
            "type": replication.type,
            "sync_schedule": replication.sync_schedule,
            "created_at": datetime.now().isoformat()
        }
        replications.append(new_replication)
        write_replications(replications)
    
    try:
        cron_manager = CrontabManager()
        cron_success = cron_manager.add_replication_job(
            new_replication["id"],
            new_replication["sync_schedule"],
            new_replication["name"],
        )

        if not cron_success:
            with REPLICATIONS_LOCK:
                remaining = [
                    item
                    for item in read_replications()
                    if item["id"] != new_replication["id"]
                ]
                write_replications(remaining)
            raise HTTPException(status_code=500, detail="Failed to schedule replication job")

    except HTTPException:
        raise
    except Exception as e:
        with REPLICATIONS_LOCK:
            remaining = [
                item
                for item in read_replications()
                if item["id"] != new_replication["id"]
            ]
            write_replications(remaining)
        _clog(f"[REPLICATION] Error scheduling cron job: {e}", error=True)
        raise HTTPException(status_code=500, detail=f"Failed to schedule replication job: {e}")

    _clog(f"[REPLICATION] Created replication: {replication.name} from {replication.origin_node} to {replication.destination_node}")
    
    return new_replication

@router.delete("/cluster/replications/{replication_id}")
async def delete_replication(replication_id: str):
    """Delete a replication rule"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can manage replications")
    
    with REPLICATIONS_LOCK:
        replications = read_replications()
        replication_to_delete = next(
            (item for item in replications if item["id"] == replication_id),
            None,
        )
        if not replication_to_delete:
            raise HTTPException(status_code=404, detail="Replication not found")
        updated_replications = [r for r in replications if r["id"] != replication_id]
        write_replications(updated_replications)
    
    # Remove cron job for this replication
    try:
        cron_manager = CrontabManager()
        cron_manager.remove_replication_job(replication_id)
        _clog(f"[REPLICATION] Removed cron job for replication: {replication_id}")
    except Exception as e:
        _clog(f"[REPLICATION] Error removing cron job: {e}", error=True)
        # Log error but don't fail the deletion
    
    _clog(f"[REPLICATION] Deleted replication: {replication_id}")
    
    return {"message": "Replication deleted successfully"}

@router.post("/cluster/replications/{replication_id}/trigger", status_code=202)
async def trigger_replication(replication_id: str):
    """Manually trigger a replication"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can trigger replications")
    
    replications = read_replications()
    
    replication = None
    for r in replications:
        if r["id"] == replication_id:
            replication = r
            break
    
    if not replication:
        raise HTTPException(status_code=404, detail="Replication not found")
    
    _clog(f"[REPLICATION] Queueing replication: {replication['name']} from {replication['origin_node']} to {replication['destination_node']}")
    persistent_job = enqueue_job(
        "replication",
        {"replication_id": replication_id},
        idempotency_key=f"replication:{replication_id}",
        resource_type="replication",
        resource_id=replication_id,
    )
    return {
        "message": "Replication queued",
        "replication": replication,
        "persistent_job": persistent_job,
    }


@router.get("/cluster/replications/{replication_id}/progress")
async def get_replication_progress(replication_id: str):
    """Get latest progress for one replication rule."""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can view replication progress")

    job = find_latest_job("replication", replication_id)
    if not job:
        return {
            "replication_id": replication_id,
            "status": "idle",
            "progress": 0,
            "message": "No active replication",
            "updated_at": None,
        }
    return {
        "replication_id": replication_id,
        "persistent_job_id": job["id"],
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "error": job["error"],
        "result": job["result"],
        "updated_at": job["updated_at"],
    }

async def execute_replication(replication: dict, progress_callback=None):
    """Execute the actual replication process"""
    replication_id = replication.get("id", "unknown")

    def _progress(value: int, message: str, status: str = "running"):
        if progress_callback is not None:
            progress_callback(value, message, status)
        set_progress(
            "replications",
            replication_id,
            status=status,
            progress=value,
            message=message,
            extra={"replication_id": replication_id, "name": replication.get("name")},
        )

    try:
        _clog(f"[REPLICATION] Starting replication: {replication['name']}")
        _progress(5, "Replication initialized")
        
        origin_node = replication['origin_node']
        destination_node = replication['destination_node']
        resource_name = replication['name']
        resource_type = replication['type']
        notify(
            "replication_started",
            f"Replication '{resource_name}' started | Type: {resource_type} | From: {origin_node} | To: {destination_node}",
        )
        
        master_config = read_master_config()
        if not master_config:
            _clog(f"[REPLICATION] No master config found")
            _progress(100, "Master configuration missing", status="failed")
            return False
        
        cluster_key = master_config.get("key")
        if not cluster_key:
            _clog(f"[REPLICATION] No cluster key found in config")
            _progress(100, "Cluster key missing", status="failed")
            return False
        
        _clog(f"[REPLICATION] Cluster key loaded successfully")
        
        local_tls = ensure_node_tls()
        origin_config = (
            {
                "hostname": get_hostname(),
                "ip_address": "127.0.0.1",
                "port": CLUSTER_TLS_PORT,
                "tls_ca_certificate": local_tls.ca_certificate,
            }
            if origin_node == get_hostname()
            else read_node_config(origin_node)
        )
        dest_config = (
            {
                "hostname": get_hostname(),
                "ip_address": "127.0.0.1",
                "port": CLUSTER_TLS_PORT,
                "tls_ca_certificate": local_tls.ca_certificate,
            }
            if destination_node == get_hostname()
            else read_node_config(destination_node)
        )

        if not origin_config:
            _clog(f"[REPLICATION] Origin node config not found: {origin_node}")
            _progress(100, f"Origin node not found: {origin_node}", status="failed")
            return False
        if not dest_config:
            _clog(f"[REPLICATION] Destination node config not found: {destination_node}")
            _progress(100, f"Destination node not found: {destination_node}", status="failed")
            return False

        origin_ip = origin_config["ip_address"]
        dest_ip = dest_config["ip_address"]
        origin_ca, origin_port, _ = await _resolve_peer_tls(
            origin_config,
            cluster_key,
            expected_node_id=origin_node,
        )
        dest_ca, dest_port, _ = await _resolve_peer_tls(
            dest_config,
            cluster_key,
            expected_node_id=destination_node,
        )

        _clog(f"[REPLICATION] Exporting {resource_type} '{resource_name}' from {origin_ip}:{origin_port}")
        _progress(20, "Exporting from origin node")

        export_url = cluster_url(
            origin_ip,
            origin_port,
            f"/cluster/export/{resource_type}/{resource_name}",
        )
        _clog(f"[REPLICATION] Export URL: {export_url}")
        export_response = await signed_cluster_request(
            "POST",
            export_url,
            key=cluster_key,
            ca_certificate=origin_ca,
            timeout=300.0,
        )
        if export_response.status_code not in (200, 202):
            _progress(100, "Export failed", status="failed")
            return False

        export_data = export_response.json()
        remote_job = export_data.get("persistent_job")
        if remote_job:
            remote_job_id = remote_job.get("id")
            if not remote_job_id:
                _progress(100, "Export job response was invalid", status="failed")
                return False
            status_url = cluster_url(
                origin_ip,
                origin_port,
                f"/cluster/jobs/{remote_job_id}",
            )
            export_deadline = time.monotonic() + (4 * 60 * 60)
            while time.monotonic() < export_deadline:
                _progress(30, "Waiting for origin export job")
                status_response = await signed_cluster_request(
                    "GET",
                    status_url,
                    key=cluster_key,
                    ca_certificate=origin_ca,
                    timeout=30.0,
                )
                if status_response.status_code != 200:
                    _progress(100, "Could not read export job", status="failed")
                    return False
                remote_job = status_response.json()
                if remote_job.get("status") == "completed":
                    export_data = remote_job.get("result") or {}
                    break
                if remote_job.get("status") in {"failed", "cancelled"}:
                    _progress(100, "Origin export job failed", status="failed")
                    return False
                await asyncio.sleep(2)
            else:
                _progress(100, "Origin export job timed out", status="failed")
                return False

        export_path = export_data.get("export_path")
        if not export_path:
            _progress(100, "No export path returned", status="failed")
            return False

        download_url = cluster_url(
            origin_ip,
            origin_port,
            f"/cluster/download/{export_path.split('/')[-1]}",
        )
        _progress(45, "Downloading export archive")
        download_response = await signed_cluster_request(
            "GET",
            download_url,
            key=cluster_key,
            ca_certificate=origin_ca,
            timeout=300.0,
        )
        if download_response.status_code != 200:
            _progress(100, "Download failed", status="failed")
            return False

        archive_data = download_response.content
        upload_url = cluster_url(dest_ip, dest_port, "/cluster/upload")
        _progress(65, "Uploading archive to destination node")
        upload_response = await signed_cluster_request(
            "POST",
            upload_url,
            key=cluster_key,
            ca_certificate=dest_ca,
            content=archive_data,
            headers={
                "Content-Type": "application/gzip",
                "X-UpservX-Filename": f"{resource_name}.tar.gz",
            },
            timeout=300.0,
        )
        if upload_response.status_code != 200:
            _progress(100, "Upload failed", status="failed")
            return False

        uploaded_path = upload_response.json().get("path")
        import_url = cluster_url(
            dest_ip,
            dest_port,
            f"/cluster/import/{resource_type}",
        )
        _progress(85, "Importing on destination node")
        import_response = await signed_cluster_request(
            "POST",
            import_url,
            key=cluster_key,
            ca_certificate=dest_ca,
            params={"archive_path": uploaded_path, "name": resource_name},
            timeout=300.0,
        )
        if import_response.status_code != 200:
            _progress(100, "Import failed", status="failed")
            return False

        _clog(f"[REPLICATION] Successfully replicated {resource_type} '{resource_name}' from {origin_node} to {destination_node}")
        _progress(100, "Replication completed successfully", status="completed")
        notify(
            "replication_success",
            f"Replication '{resource_name}' completed | Type: {resource_type} | From: {origin_node} | To: {destination_node}",
        )
        return True
            
    except Exception as e:
        _clog(f"[REPLICATION] Error during replication: {e}", error=True)
        _progress(100, f"Error: {e}", status="failed")
        notify(
            "replication_failure",
            f"Replication '{replication.get('name', 'unknown')}' failed | Type: {replication.get('type', 'unknown')} | Error: {e}",
        )

        import traceback
        traceback.print_exc()
    return False

@router.get("/cluster/nodes/{hostname}/resources")
async def get_node_resources(hostname: str):
    """Get containers and VMs available on a specific node"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can query node resources")
    
    _clog(f"[REPLICATION] Fetching resources from node: {hostname}")
    
    if hostname == get_hostname():
        try:
            from handlers.containers import list_all_containers
            from handlers.vms import list_vms_with_status
            
            containers = list_all_containers(include_compose=False)
            vms = list_vms_with_status()
            
            resources = []
            for container in containers:
                if container.name and container.name.strip():
                    resources.append({
                        "name": container.name,
                        "type": "container"
                    })
            
            for vm in vms:
                if vm.name and vm.name.strip():
                    resources.append({
                        "name": vm.name,
                        "type": "vm"
                    })
            
            _clog(f"[REPLICATION] Found {len(resources)} resources on local node")
            return {"resources": resources}
        except Exception as e:
            _clog(f"[REPLICATION] Error getting local resources: {e}", error=True)

            import traceback
            traceback.print_exc()
            return {"resources": []}
    
    node_config = read_node_config(hostname)
    if not node_config:
        _clog(f"[REPLICATION] Node config not found for: {hostname}")
        raise HTTPException(status_code=404, detail="Node not found")
    
    try:
        master_config = read_master_config()
        cluster_key = master_config.get("key")
        node_ip = node_config['ip_address']
        ca_certificate, node_port, _ = await _resolve_peer_tls(
            node_config,
            cluster_key,
            expected_node_id=hostname,
        )
        
        _clog(f"[REPLICATION] Fetching from {node_ip}:{node_port}")
        
        resources = []
        
        try:
            containers_url = cluster_url(node_ip, node_port, "/containers")
            _clog(f"[REPLICATION] Fetching containers from: {containers_url}")
            containers_response = await signed_cluster_request(
                "GET",
                containers_url,
                key=cluster_key,
                ca_certificate=ca_certificate,
                params={"include_compose": "false"},
                timeout=10.0,
            )
                
            _clog(f"[REPLICATION] Containers response status: {containers_response.status_code}")
                
            if containers_response.status_code == 200:
                containers = containers_response.json()
                _clog(f"[REPLICATION] Found {len(containers)} containers")
                for container in containers:
                    name = container.get("name")
                    if name and name.strip():
                        resources.append({"name": name, "type": "container"})
            else:
                _clog(f"[REPLICATION] Failed to fetch containers: {containers_response.text}", error=True)

        except Exception as e:
            _clog(f"[REPLICATION] Error fetching containers: {e}", error=True)

        try:
            vms_url = cluster_url(node_ip, node_port, "/vms")
            _clog(f"[REPLICATION] Fetching VMs from: {vms_url}")
            vms_response = await signed_cluster_request(
                "GET",
                vms_url,
                key=cluster_key,
                ca_certificate=ca_certificate,
                timeout=10.0,
            )
                
            _clog(f"[REPLICATION] VMs response status: {vms_response.status_code}")
                
            if vms_response.status_code == 200:
                vms = vms_response.json()
                _clog(f"[REPLICATION] Found {len(vms)} VMs")
                for vm in vms:
                    name = vm.get("name")
                    if name and name.strip():
                        resources.append({"name": name, "type": "vm"})
            else:
                _clog(f"[REPLICATION] Failed to fetch VMs: {vms_response.text}", error=True)

        except Exception as e:
            _clog(f"[REPLICATION] Error fetching VMs: {e}", error=True)

        
        _clog(f"[REPLICATION] Total resources found: {len(resources)}")
        return {"resources": resources}
    except Exception as e:
        _clog(f"[REPLICATION] Error fetching resources from {hostname}: {e}", error=True)

        import traceback
        traceback.print_exc()
        return {"resources": []}

# Replication Export/Import Endpoints
TEMP_EXPORT_DIR = "/tmp/upservx_exports"

def _safe_tar_extractall(tar, dest_dir: str):
    """Extract tar archive, rejecting any members that escape dest_dir (path traversal)."""
    dest_real = os.path.realpath(dest_dir)
    for member in tar.getmembers():
        member_path = os.path.realpath(os.path.join(dest_real, member.name))
        if not member_path.startswith(dest_real + os.sep) and member_path != dest_real:
            raise Exception(f"Path traversal detected in archive member: {member.name}")
    tar.extractall(dest_dir)

async def _export_resource_now(resource_type: str, resource_name: str):
    """Export a container or VM with all volumes/storage"""
    _clog(f"[EXPORT] Called with resource_type={resource_type}, resource_name={resource_name}")
    
    try:
        os.makedirs(TEMP_EXPORT_DIR, exist_ok=True)
        import uuid
        export_id = str(uuid.uuid4())
        export_path = os.path.join(TEMP_EXPORT_DIR, f"{export_id}.tar.gz")
        
        _clog(f"[EXPORT] Exporting {resource_type} '{resource_name}' to {export_path}")
        
        if resource_type == "container":
            import tarfile
            
            inspect_result = subprocess.run(
                ["docker", "inspect", resource_name],
                capture_output=True,
                text=True,
                check=True
            )
            
            container_info = json.loads(inspect_result.stdout)[0]
            
            with tarfile.open(export_path, "w:gz") as tar:
                _clog(f"[EXPORT] Exporting container filesystem...")
                export_result = subprocess.run(
                    ["docker", "export", resource_name],
                    capture_output=True,
                    check=True
                )
                
                fs_temp = os.path.join(TEMP_EXPORT_DIR, f"{export_id}_filesystem.tar")
                with open(fs_temp, 'wb') as f:
                    f.write(export_result.stdout)
                
                tar.add(fs_temp, arcname="filesystem.tar")
                
                mounts = container_info.get("Mounts", [])
                volumes_info = []
                
                for mount in mounts:
                    if mount.get("Type") == "volume":
                        volume_name = mount.get("Name")
                        mount_point = mount.get("Destination")
                        
                        _clog(f"[EXPORT] Exporting volume: {volume_name}")
                        
                        vol_inspect = subprocess.run(
                            ["docker", "volume", "inspect", volume_name],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        
                        vol_info = json.loads(vol_inspect.stdout)[0]
                        volume_path = vol_info.get("Mountpoint")
                        
                        if volume_path and os.path.exists(volume_path):
                            tar.add(volume_path, arcname=f"volumes/{volume_name}")
                            volumes_info.append({
                                "name": volume_name,
                                "destination": mount_point
                            })
                
                host_config = container_info.get("HostConfig", {})
                metadata = {
                    "name": resource_name,
                    "image": container_info.get("Config", {}).get("Image"),
                    "env": container_info.get("Config", {}).get("Env", []),
                    "cmd": container_info.get("Config", {}).get("Cmd"),
                    "volumes": volumes_info,
                    "ports": container_info.get("NetworkSettings", {}).get("Ports", {}),
                    "port_bindings": host_config.get("PortBindings", {}),
                    "restart_policy": host_config.get("RestartPolicy", {}),
                    "exposed_ports": container_info.get("Config", {}).get("ExposedPorts", {})
                }
                
                metadata_file = os.path.join(TEMP_EXPORT_DIR, f"{export_id}_metadata.json")
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                tar.add(metadata_file, arcname="metadata.json")
                
                image_name = container_info.get("Config", {}).get("Image")
                if image_name:
                    _clog(f"[EXPORT] Exporting Docker image: {image_name}")
                    image_export_result = subprocess.run(
                        ["docker", "save", image_name],
                        capture_output=True,
                        check=True
                    )
                    
                    image_temp = os.path.join(TEMP_EXPORT_DIR, f"{export_id}_image.tar")
                    with open(image_temp, 'wb') as f:
                        f.write(image_export_result.stdout)
                    
                    tar.add(image_temp, arcname="image.tar")
                    os.remove(image_temp)
                    _clog(f"[EXPORT] Image exported successfully")
                
                os.remove(fs_temp)
            
            _clog(f"[EXPORT] Container exported successfully with {len(volumes_info)} volumes")
            
        elif resource_type == "vm":
            import tarfile
            import xml.etree.ElementTree as ET
            
            _clog(f"[EXPORT] Getting VM XML definition for: {resource_name}")
            xml_result = subprocess.run(
                ["virsh", "dumpxml", resource_name],
                capture_output=True,
                text=True,
                check=True
            )
            vm_xml = xml_result.stdout
            
            disk_paths = []
            try:
                root = ET.fromstring(vm_xml)
                for disk in root.findall(".//disk[@type='file']"):
                    source = disk.find("source")
                    if source is not None:
                        disk_file = source.get("file")
                        if disk_file and os.path.exists(disk_file):
                            disk_paths.append(disk_file)
                            _clog(f"[EXPORT] Found disk: {disk_file}")
            except Exception as e:
                _clog(f"[EXPORT] Warning: Could not parse disk paths from XML: {e}")
            
            if not disk_paths:
                raise HTTPException(status_code=404, detail=f"No disk images found for VM '{resource_name}'")
            
            with tarfile.open(export_path, "w:gz") as tar:
                xml_temp = os.path.join(TEMP_EXPORT_DIR, f"{export_id}_vm.xml")
                with open(xml_temp, 'w') as f:
                    f.write(vm_xml)
                tar.add(xml_temp, arcname="vm.xml")
                os.remove(xml_temp)
                
                for i, disk_path in enumerate(disk_paths):
                    disk_filename = os.path.basename(disk_path)
                    _clog(f"[EXPORT] Adding disk image: {disk_path} ({os.path.getsize(disk_path) // 1024 // 1024} MB)")
                    tar.add(disk_path, arcname=f"disks/{disk_filename}")
                
                vm_metadata = {
                    "name": resource_name,
                    "disk_paths": disk_paths,
                    "disk_filenames": [os.path.basename(p) for p in disk_paths]
                }
                metadata_file = os.path.join(TEMP_EXPORT_DIR, f"{export_id}_vm_metadata.json")
                with open(metadata_file, 'w') as f:
                    json.dump(vm_metadata, f)
                tar.add(metadata_file, arcname="vm_metadata.json")
                os.remove(metadata_file)
            
            _clog(f"[EXPORT] VM exported successfully with {len(disk_paths)} disk(s)")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown resource type: {resource_type}")
        
        return {
            "export_path": export_path,
            "export_id": export_id
        }
        
    except HTTPException:
        raise
    except subprocess.CalledProcessError as e:
        _clog(f"[EXPORT] Command failed: {e.stderr if e.stderr else str(e)}", error=True)

        raise HTTPException(status_code=500, detail=f"Export failed: {e.stderr if e.stderr else str(e)}")
    except Exception as e:
        _clog(f"[EXPORT] Export failed: {e}", error=True)

        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@router.post("/cluster/export/{resource_type}/{resource_name}", status_code=202)
async def export_resource(resource_type: str, resource_name: str):
    """Queue a cluster transport export outside the API process."""
    if resource_type not in {"container", "vm"}:
        raise HTTPException(status_code=400, detail="Unknown resource type")
    if (
        not resource_name
        or resource_name in {".", ".."}
        or os.path.basename(resource_name) != resource_name
    ):
        raise HTTPException(status_code=400, detail="Invalid resource name")
    job = enqueue_job(
        "cluster_export",
        {"resource_type": resource_type, "resource_name": resource_name},
        idempotency_key=f"cluster-export:{resource_type}:{resource_name}",
        resource_type="cluster_export",
        resource_id=f"{resource_type}:{resource_name}",
    )
    return {"message": "Export queued", "persistent_job": job}


@router.get("/cluster/jobs/{job_id}")
async def get_cluster_transport_job(job_id: str):
    """Return status for a signed inter-node transport job."""
    job = get_job(job_id)
    if job is None or job.get("kind") != "cluster_export":
        raise HTTPException(status_code=404, detail="Cluster transport job not found")
    return job


@router.get("/cluster/download/{filename}")
async def download_export(filename: str):
    """Download an exported archive"""
    if (
        not filename
        or filename in {".", ".."}
        or os.path.basename(filename) != filename
    ):
        raise HTTPException(status_code=400, detail="Invalid export filename")
    
    file_path = os.path.join(TEMP_EXPORT_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Export file not found")
    
    _clog(f"[DOWNLOAD] Serving: {file_path}")
    
    from fastapi.responses import FileResponse
    return FileResponse(
        file_path,
        media_type="application/gzip",
        filename=filename
    )

@router.post("/cluster/upload")
async def upload_archive(request: Request):
    """Upload an archive for import"""
    try:
        os.makedirs(TEMP_EXPORT_DIR, exist_ok=True)

        filename = request.headers.get("X-UpservX-Filename", "")
        if (
            not filename
            or filename in {".", ".."}
            or os.path.basename(filename) != filename
        ):
            raise HTTPException(status_code=400, detail="Invalid upload filename")
        
        import uuid
        upload_id = str(uuid.uuid4())
        upload_path = os.path.join(TEMP_EXPORT_DIR, f"{upload_id}_{filename}")
        
        _clog(f"[UPLOAD] Receiving file: {filename}")
        
        with open(upload_path, "wb") as f:
            content = await request.body()
            f.write(content)
        
        _clog(f"[UPLOAD] Saved to: {upload_path} ({len(content)} bytes)")
        
        return {
            "path": upload_path,
            "filename": filename
        }
    except HTTPException:
        raise
    except Exception as e:
        _clog(f"[UPLOAD] Upload failed: {e}", error=True)

        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/cluster/import/{resource_type}")
async def import_resource(resource_type: str, archive_path: str = "", name: str = ""):
    """Import a container or VM from archive"""
    try:
        if resource_type not in {"container", "vm"}:
            raise HTTPException(status_code=400, detail="Unknown resource type")
        if not name or name in {".", ".."} or os.path.basename(name) != name:
            raise HTTPException(status_code=400, detail="Invalid resource name")
        export_root = os.path.realpath(TEMP_EXPORT_DIR)
        resolved_archive_path = os.path.realpath(archive_path)
        if not resolved_archive_path.startswith(export_root + os.sep):
            raise HTTPException(status_code=400, detail="Archive path is outside export storage")
        if not os.path.isfile(resolved_archive_path):
            raise HTTPException(status_code=404, detail="Archive not found")
        archive_path = resolved_archive_path
        
        _clog(f"[IMPORT] Importing {resource_type} '{name}' from {archive_path}")
        
        if resource_type == "container":
            import tarfile
            
            extract_dir = os.path.join(TEMP_EXPORT_DIR, f"extract_{name}")
            os.makedirs(extract_dir, exist_ok=True)
            
            _clog(f"[IMPORT] Extracting archive...")
            with tarfile.open(archive_path, "r:gz") as tar:
                _safe_tar_extractall(tar, extract_dir)
            
            metadata_file = os.path.join(extract_dir, "metadata.json")
            if not os.path.exists(metadata_file):
                raise HTTPException(status_code=400, detail="Metadata not found in archive")
            
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            image_path = os.path.join(extract_dir, "image.tar")
            if os.path.exists(image_path):
                _clog(f"[IMPORT] Loading Docker image...")
                with open(image_path, 'rb') as f:
                    load_result = subprocess.run(
                        ["docker", "load"],
                        input=f.read(),
                        capture_output=True,
                        check=True
                    )
                _clog(f"[IMPORT] Image loaded: {load_result.stdout.decode().strip()}")
                
                # Use the original image name from metadata
                image_to_use = metadata.get("image")
            else:
                # Fallback: Import container filesystem as image
                _clog(f"[IMPORT] No image.tar found, importing container filesystem...")
                fs_path = os.path.join(extract_dir, "filesystem.tar")
                
                with open(fs_path, 'rb') as f:
                    import_result = subprocess.run(
                        ["docker", "import", "-", name],
                        input=f.read(),
                        capture_output=True,
                        check=True
                    )
                
                image_to_use = import_result.stdout.decode().strip()
                _clog(f"[IMPORT] Created image from filesystem: {image_to_use}")
            
            volumes_info = metadata.get("volumes", [])
            volume_mounts = []
            
            for vol_info in volumes_info:
                volume_name = vol_info["name"]
                mount_point = vol_info["destination"]
                
                _clog(f"[IMPORT] Restoring volume: {volume_name}")
                
                subprocess.run(
                    ["docker", "volume", "create", volume_name],
                    capture_output=True,
                    check=True
                )
                
                vol_inspect = subprocess.run(
                    ["docker", "volume", "inspect", volume_name],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                vol_data = json.loads(vol_inspect.stdout)[0]
                volume_path = vol_data.get("Mountpoint")
                
                source_path = os.path.join(extract_dir, f"volumes/{volume_name}")
                if os.path.exists(source_path) and volume_path:
                    subprocess.run(
                        ["cp", "-a", f"{source_path}/.", volume_path],
                        check=True
                    )
                    _clog(f"[IMPORT] Restored volume data to {volume_path}")
                
                volume_mounts.append(f"{volume_name}:{mount_point}")
            
            _clog(f"[IMPORT] Creating container with volumes and port mappings...")
            
            create_cmd = ["docker", "create", "--name", name]
            
            port_bindings = metadata.get("port_bindings", {})
            if port_bindings:
                for container_port, host_bindings in port_bindings.items():
                    if host_bindings:
                        for binding in host_bindings:
                            host_port = binding.get("HostPort")
                            host_ip = binding.get("HostIp", "")
                            if host_port:
                                if host_ip:
                                    create_cmd.extend(["-p", f"{host_ip}:{host_port}:{container_port}"])
                                else:
                                    create_cmd.extend(["-p", f"{host_port}:{container_port}"])
                                _clog(f"[IMPORT] Adding port mapping: {host_port}:{container_port}")
            
            for mount in volume_mounts:
                create_cmd.extend(["-v", mount])
            
            for env in metadata.get("env", []):
                create_cmd.extend(["-e", env])
            
            restart_policy = metadata.get("restart_policy", {})
            if restart_policy and restart_policy.get("Name") != "no":
                policy_name = restart_policy.get("Name", "no")
                create_cmd.extend(["--restart", policy_name])
            
            create_cmd.append(image_to_use)
            
            if metadata.get("cmd"):
                create_cmd.extend(metadata["cmd"])
            
            subprocess.run(create_cmd, capture_output=True, check=True)
            
            _clog(f"[IMPORT] Container created successfully")
            
            shutil.rmtree(extract_dir)
            os.remove(archive_path)
            
        elif resource_type == "vm":
            import tarfile
            import xml.etree.ElementTree as ET
            
            extract_dir = os.path.join(TEMP_EXPORT_DIR, f"extract_{name}")
            os.makedirs(extract_dir, exist_ok=True)
            
            _clog(f"[IMPORT] Extracting VM archive...")
            with tarfile.open(archive_path, "r:gz") as tar:
                _safe_tar_extractall(tar, extract_dir)
            
            metadata_file = os.path.join(extract_dir, "vm_metadata.json")
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    vm_metadata = json.load(f)
            else:
                vm_metadata = {}
            
            disks_dir = os.path.join(extract_dir, "disks")
            disk_map = {}  # old filename -> new path
            
            if os.path.exists(disks_dir):
                for disk_filename in os.listdir(disks_dir):
                    src = os.path.join(disks_dir, disk_filename)
                    dst = f"/var/lib/libvirt/images/{disk_filename}"
                    shutil.move(src, dst)
                    disk_map[disk_filename] = dst
                    _clog(f"[IMPORT] Moved disk: {disk_filename} -> {dst}")
            
            xml_file = os.path.join(extract_dir, "vm.xml")
            if not os.path.exists(xml_file):
                raise HTTPException(status_code=400, detail="VM XML definition not found in archive")
            
            with open(xml_file, 'r') as f:
                vm_xml = f.read()
            
            # Update disk paths in XML to point to new locations
            try:
                root = ET.fromstring(vm_xml)
                for disk in root.findall(".//disk[@type='file']"):
                    source = disk.find("source")
                    if source is not None:
                        old_path = source.get("file", "")
                        old_filename = os.path.basename(old_path)
                        if old_filename in disk_map:
                            source.set("file", disk_map[old_filename])
                            _clog(f"[IMPORT] Updated disk path: {old_path} -> {disk_map[old_filename]}")
                
                # Update VM name
                name_el = root.find("name")
                if name_el is not None:
                    name_el.text = name
                
                # Remove UUID so libvirt generates a new one
                uuid_el = root.find("uuid")
                if uuid_el is not None:
                    root.remove(uuid_el)
                
                vm_xml = ET.tostring(root, encoding='unicode')
            except Exception as e:
                _clog(f"[IMPORT] Warning: Could not patch VM XML: {e}")
            
            patched_xml_file = os.path.join(extract_dir, "vm_patched.xml")
            with open(patched_xml_file, 'w') as f:
                f.write(vm_xml)
            
            _clog(f"[IMPORT] Defining VM in libvirt...")
            define_result = subprocess.run(
                ["virsh", "define", patched_xml_file],
                capture_output=True,
                text=True,
                check=True
            )
            _clog(f"[IMPORT] VM defined: {define_result.stdout.strip()}")
            
            shutil.rmtree(extract_dir)
            os.remove(archive_path)
            
            _clog(f"[IMPORT] VM imported and defined successfully")
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown resource type: {resource_type}")
        
        return {
            "message": f"{resource_type.capitalize()} imported successfully",
            "name": name
        }

    except HTTPException:
        raise
    except subprocess.CalledProcessError as e:
        _clog(f"[IMPORT] Command failed: {e.stderr if e.stderr else str(e)}", error=True)

        raise HTTPException(status_code=500, detail=f"Import failed: {e.stderr if e.stderr else str(e)}")
    except Exception as e:
        _clog(f"[IMPORT] Import failed: {e}", error=True)

        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
