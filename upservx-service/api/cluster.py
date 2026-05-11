from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Header
from pydantic import BaseModel
from typing import List, Optional
import secrets
import socket
import psutil
from datetime import datetime
import json
import os
import shutil
import subprocess
import httpx
from lib.load_balancer import get_load_balancer, LoadBalancingStrategy
from lib.container_sync import get_sync_manager, SyncRule, SyncStrategy
from lib.metrics_collector import get_metrics_collector
from lib.logger import log_system
from lib.progress_tracker import get_progress, set_progress

def _clog(msg: str, error: bool = False) -> None:
    """Print to console AND write to activity log file."""
    print(msg)
    log_system(msg, error=error)

router = APIRouter()

# Paths for cluster configuration
UPSERVX_CONFIG_DIR = "/etc/upservx"
MASTER_CONFIG_FILE = os.path.join(UPSERVX_CONFIG_DIR, "master")
CHILD_CONFIG_FILE = os.path.join(UPSERVX_CONFIG_DIR, "child")
NODES_DIR = os.path.join(UPSERVX_CONFIG_DIR, "nodes")

def verify_cluster_auth(authorization: str = Header(None)):
    """Verify cluster authentication from Authorization header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    provided_key = authorization[7:]  # Remove "Bearer " prefix
    
    master_config = read_master_config()
    if master_config and master_config.get("key") == provided_key:
        return True
    
    child_config = read_child_config()
    if child_config:
        stored_key = child_config.get("cluster_key") or child_config.get("key")
        if stored_key == provided_key:
            return True
    
    raise HTTPException(status_code=401, detail="Invalid cluster key")

class ClusterCreateRequest(BaseModel):
    cluster_name: str

class ClusterJoinRequest(BaseModel):
    master_ip: str
    token: str
    port: int = 9500

class NodeRegistrationRequest(BaseModel):
    hostname: str
    ip_address: str
    port: int
    cluster_key: str
    resources: dict = {}

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
    cluster_token: Optional[str] = None
    nodes: List[ClusterNode]

def ensure_config_dir():
    """Ensure configuration directory exists"""
    try:
        os.makedirs(UPSERVX_CONFIG_DIR, exist_ok=True)
        os.makedirs(NODES_DIR, exist_ok=True)
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
    with open(MASTER_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def read_child_config():
    """Read child configuration file"""
    if os.path.exists(CHILD_CONFIG_FILE):
        with open(CHILD_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None

def write_child_config(config: dict):
    """Write child configuration file"""
    ensure_config_dir()
    with open(CHILD_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def read_node_config(hostname: str):
    """Read a specific node configuration"""
    node_file = os.path.join(NODES_DIR, f"{hostname}.json")
    if os.path.exists(node_file):
        with open(node_file, 'r') as f:
            return json.load(f)
    return None

def find_unique_hostname(base_hostname: str) -> str:
    """Find a unique hostname by appending -2, -3, etc. if hostname already exists"""
    hostname = base_hostname
    counter = 2
    
    while read_node_config(hostname) is not None:
        hostname = f"{base_hostname}-{counter}"
        counter += 1
        _clog(f"[CLUSTER] Hostname {base_hostname} exists, trying {hostname}")
    
    return hostname

def write_node_config(hostname: str, config: dict):
    """Write node configuration file"""
    ensure_config_dir()
    node_file = os.path.join(NODES_DIR, f"{hostname}.json")
    _clog(f"[CLUSTER] Writing node config to {node_file}")
    try:
        with open(node_file, 'w') as f:
            json.dump(config, f, indent=2)
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
    node_file = os.path.join(NODES_DIR, f"{hostname}.json")
    if os.path.exists(node_file):
        os.remove(node_file)

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

async def fetch_node_metrics(ip_address: str, port: int, cluster_key: str):
    """Fetch metrics from a child node"""
    try:
        url = f"http://{ip_address}:{port}/cluster/node/metrics"
        _clog(f"[CLUSTER] Fetching metrics from {url}")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {cluster_key}"}
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
                    # Looks like GB value, convert to bytes
                    memory_total = int(memory_total * (1024**3))
                
                memory_available = metrics.get("memory", {}).get("available", 0)
                if memory_available == 0:
                    # Calculate from used if available not provided
                    memory_used = metrics.get("memory", {}).get("used", 0)
                    if isinstance(memory_used, float) and memory_used < 1000:
                        memory_used = int(memory_used * (1024**3))
                    memory_available = memory_total - memory_used
                
                # Extract container information
                containers = metrics.get("containers", {})
                running_containers = containers.get("running", 0)
                total_containers = containers.get("total", 0)
                
                # Extract VM information
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
                    "success": True
                }
                _clog(f"[CLUSTER] Extracted values: cpu_count={extracted['cpu_count']}, memory_total={extracted['memory_total']}")
                return extracted
            else:
                _clog(f"[CLUSTER] Failed to fetch metrics from {ip_address}: HTTP {response.status_code}", error=True)

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
        debug_info["master_config"] = read_master_config()
        debug_info["stored_nodes"] = list_all_nodes()
    
    if is_child_node():
        debug_info["child_config"] = read_child_config()
    
    return debug_info

@router.post("/cluster/test-write")
async def test_write_permissions():
    """Test if we can write to the nodes directory"""
    ensure_config_dir()
    
    test_file = os.path.join(NODES_DIR, "test_write.json")
    test_data = {"test": "data", "timestamp": datetime.now().isoformat()}
    
    try:
        with open(test_file, 'w') as f:
            json.dump(test_data, f, indent=2)
        
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
    cluster_token = None
    
    if is_master:
        master_config = read_master_config()
        cluster_token = master_config.get("key")
        master_ip = get_local_ip()
        
        master_resources = get_system_resources()

        master_node = {
            "id": get_hostname(),
            "hostname": get_hostname(),
            "ip_address": get_local_ip(),
            "port": 9500,
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
                resources = await fetch_node_metrics(
                    node.get("ip_address"),
                    node.get("port", 9500),
                    cluster_token
                )
                
                node["resources"] = resources
                node["last_seen"] = datetime.now().isoformat()
                write_node_config(node.get("hostname"), node)
                
                is_online = resources.pop("success", False)
                
                nodes.append({
                    "id": node.get("hostname"),
                    "hostname": node.get("hostname"),
                    "ip_address": node.get("ip_address"),
                    "port": node.get("port", 9500),
                    "status": "online" if is_online else "offline",
                    "role": "child",
                    "resources": resources,
                    "last_seen": node.get("last_seen", "")
                })
    
    elif is_child:
        child_config = read_child_config()
        master_ip = child_config.get("master_ip")
        master_port = child_config.get("master_port", 9500)
        cluster_token = child_config.get("key")
        
        _clog(f"[CLUSTER] Child node trying to fetch master info from {master_ip}:{master_port}")
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"http://{master_ip}:{master_port}/cluster/node/metrics",
                    headers={"Authorization": f"Bearer {cluster_token}"}
                )
                if response.status_code == 200:
                    master_metrics = response.json()
                    _clog(f"[CLUSTER] Successfully fetched master metrics")
                    nodes.append({
                        "id": master_metrics.get("hostname", "master"),
                        "hostname": master_metrics.get("hostname", "master"),
                        "ip_address": master_ip,
                        "port": master_port,
                        "status": "online",
                        "role": "master",
                        "resources": {
                            "cpu_usage": master_metrics.get("cpu", {}).get("usage", 0),
                            "cpu_count": master_metrics.get("cpu", {}).get("count", 0),
                            "memory_usage": master_metrics.get("memory", {}).get("usage", 0),
                            "memory_total": master_metrics.get("memory", {}).get("total", 0),
                            "memory_available": master_metrics.get("memory", {}).get("available", 0),
                            "disk_usage": master_metrics.get("storage", {}).get("usage", 0),
                            "running_containers": master_metrics.get("containers", {}).get("running", 0),
                            "total_containers": master_metrics.get("containers", {}).get("total", 0),
                            "running_vms": master_metrics.get("vms", {}).get("running", 0),
                            "total_vms": master_metrics.get("vms", {}).get("total", 0)
                        },
                        "last_seen": datetime.now().isoformat()
                    })
                else:
                    _clog(f"[CLUSTER] Failed to fetch master metrics: HTTP {response.status_code}", error=True)

                    raise Exception("Master unreachable")
        except Exception as e:
            _clog(f"[CLUSTER] Master unreachable: {e}")
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
            "port": 9500,
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
        cluster_token=cluster_token,
        nodes=nodes
    )

@router.post("/cluster/create")
async def create_cluster(request: ClusterCreateRequest):
    """Create a new cluster and become master node"""
    if is_master_node():
        raise HTTPException(status_code=400, detail="This node is already a master")
    
    if is_child_node():
        raise HTTPException(status_code=400, detail="This node is already a child. Leave the cluster first")
    
    cluster_key = secrets.token_urlsafe(32)
    
    master_config = {
        "key": cluster_key,
        "cluster_name": request.cluster_name,
        "created_at": datetime.now().isoformat()
    }
    
    write_master_config(master_config)
    
    master_node_config = {
        "hostname": get_hostname(),
        "ip_address": get_local_ip(),
        "port": 9500,
        "resources": get_system_resources(),
        "last_seen": datetime.now().isoformat()
    }
    
    write_node_config(get_hostname(), master_node_config)
    
    return {
        "message": "Cluster created successfully",
        "token": cluster_key,
        "master_ip": get_local_ip()
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
    
    _clog(f"[CLUSTER] My hostname: {my_hostname}")
    _clog(f"[CLUSTER] My IP: {my_ip}")
    
    my_resources = get_system_resources()
    node_data = {
        "hostname": my_hostname,
        "ip_address": my_ip,
        "port": 9500,
        "cluster_key": request.token,
        "resources": my_resources
    }
    
    _clog(f"[CLUSTER] Attempting registration with master...")
    
    try:
        master_url = f"http://{request.master_ip}:{request.port}/cluster/register"
        _clog(f"[CLUSTER] POST {master_url}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                master_url,
                json=node_data
            )
            
            _clog(f"[CLUSTER] Response status: {response.status_code}")
            
            if response.status_code != 200:
                try:
                    error_detail = response.json().get("detail", "Failed to register with master")
                except:
                    error_detail = response.text
                _clog(f"[CLUSTER] Registration FAILED: {error_detail}", error=True)

                raise HTTPException(status_code=400, detail=f"Master rejected registration: {error_detail}")
            
            response_data = response.json()
            assigned_hostname = response_data.get("hostname", my_hostname)
            
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
    except Exception as e:
        _clog(f"[CLUSTER] Unexpected error: {type(e).__name__}: {str(e)}", error=True)

        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error during registration: {str(e)}")
    
    child_config = {
        "cluster_key": request.token,  # Store as cluster_key for consistency
        "key": request.token,  # Keep backwards compatibility
        "master_ip": request.master_ip,
        "master_port": request.port,
        "joined_at": datetime.now().isoformat(),
        "assigned_hostname": assigned_hostname
    }
    
    _clog(f"[CLUSTER] Writing child configuration...")
    write_child_config(child_config)
    _clog(f"[CLUSTER] Child configuration written to {CHILD_CONFIG_FILE}")
    _clog(f"[CLUSTER] JOIN COMPLETED SUCCESSFULLY")
    _clog(f"[CLUSTER] ========================================")
    
    return {
        "message": "Successfully joined cluster",
        "master_ip": request.master_ip,
        "assigned_hostname": assigned_hostname
    }

@router.post("/cluster/register")
async def register_node(request: NodeRegistrationRequest):
    """Register a child node with the master (master only)"""
    _clog(f"[CLUSTER] ========================================")
    _clog(f"[CLUSTER] Registration request from {request.hostname} ({request.ip_address}:{request.port})")
    _clog(f"[CLUSTER] Registration request from {request.hostname} ({request.ip_address}:{request.port})")
    
    if not is_master_node():
        _clog(f"[CLUSTER] ERROR: This node is not a master", error=True)

        raise HTTPException(status_code=403, detail="Only master node can register nodes")
    
    _clog(f"[CLUSTER] This is a master node, proceeding...")
    
    master_config = read_master_config()
    if not master_config:
        _clog(f"[CLUSTER] ERROR: Master config not found", error=True)

        raise HTTPException(status_code=500, detail="Master configuration not found")
    
    expected_key = master_config.get("key")
    
    if expected_key != request.cluster_key:
        _clog(f"[CLUSTER] ERROR: Invalid cluster key from {request.hostname}", error=True)

        raise HTTPException(status_code=401, detail="Invalid cluster key")
    
    _clog(f"[CLUSTER] Cluster key verified successfully")
    
    original_hostname = request.hostname
    all_nodes = list_all_nodes()
    
    same_ip_node = None
    for node in all_nodes:
        if node.get("ip_address") == request.ip_address:
            same_ip_node = node
            break
    
    if same_ip_node:
        existing_hostname = same_ip_node.get("hostname")
        _clog(f"[CLUSTER] Node with IP {request.ip_address} already exists as {existing_hostname}, updating...")
        same_ip_node["hostname"] = existing_hostname  # Keep the original hostname
        same_ip_node["ip_address"] = request.ip_address
        same_ip_node["port"] = request.port
        same_ip_node["resources"] = request.resources
        same_ip_node["last_seen"] = datetime.now().isoformat()
        try:
            write_node_config(existing_hostname, same_ip_node)
            _clog(f"[CLUSTER] Node {existing_hostname} updated successfully")
            return {"message": "Node updated successfully", "hostname": existing_hostname}
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
        "ip_address": request.ip_address,
        "port": request.port,
        "resources": request.resources,
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
            "original_hostname": original_hostname if unique_hostname != original_hostname else None
        }
    except Exception as e:
        _clog(f"[CLUSTER] ERROR registering node: {e}", error=True)

        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to register node: {str(e)}")

@router.post("/cluster/leave")
async def leave_cluster():
    """Leave the current cluster"""
    if not is_master_node() and not is_child_node():
        raise HTTPException(status_code=400, detail="Not part of any cluster")
    
    if is_master_node():
        if os.path.exists(MASTER_CONFIG_FILE):
            os.remove(MASTER_CONFIG_FILE)
        
        if os.path.exists(NODES_DIR):
            for filename in os.listdir(NODES_DIR):
                node_file = os.path.join(NODES_DIR, filename)
                if os.path.isfile(node_file):
                    os.remove(node_file)
        
        # TODO: Notify all child nodes
        
    elif is_child_node():
        if os.path.exists(CHILD_CONFIG_FILE):
            os.remove(CHILD_CONFIG_FILE)
        
        # TODO: Notify master node
    
    return {"message": "Successfully left cluster"}

@router.delete("/cluster/nodes/{node_id}")
async def remove_node(node_id: str):
    """Remove a node from the cluster (master only)"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can remove nodes")
    
    delete_node_config(node_id)
    
    # TODO: Notify the removed node
    
    return {"message": f"Node {node_id} removed successfully"}

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
    """Add or update container synchronization rule"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can manage sync rules")
    
    sync_manager = get_sync_manager()
    
    rule = SyncRule(
        service_name=request.service_name,
        strategy=request.strategy,
        target_nodes=request.target_nodes,
        replica_count=request.replica_count
    )
    
    sync_manager.add_sync_rule(rule)
    
    return {
        "message": f"Sync rule added for service {request.service_name}",
        "rule": rule.to_dict()
    }

@router.get("/cluster/sync/rules")
async def get_sync_rules():
    """Get all container synchronization rules"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can view sync rules")
    
    sync_manager = get_sync_manager()
    
    return {
        "rules": {
            name: rule.to_dict()
            for name, rule in sync_manager.sync_rules.items()
        }
    }

@router.delete("/cluster/sync/rules/{service_name}")
async def remove_sync_rule(service_name: str):
    """Remove container synchronization rule"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can manage sync rules")
    
    sync_manager = get_sync_manager()
    sync_manager.remove_sync_rule(service_name)
    
    return {
        "message": f"Sync rule removed for service {service_name}"
    }

@router.post("/cluster/sync/execute")
async def execute_synchronization():
    """Execute container synchronization across cluster"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can execute synchronization")
    
    cluster_info = await get_cluster_info()
    master_config = read_master_config()
    cluster_key = master_config.get("key")
    
    nodes_dict = [
        {
            "id": n.id,
            "hostname": n.hostname,
            "ip_address": n.ip_address,
            "port": n.port,
            "status": n.status
        }
        for n in cluster_info.nodes
    ]
    
    sync_manager = get_sync_manager()
    await sync_manager.sync_all_containers(nodes_dict, cluster_key)
    
    return {
        "message": "Container synchronization executed",
        "status": sync_manager.get_sync_status()
    }

@router.get("/cluster/sync/status")
async def get_sync_status():
    """Get container synchronization status"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can view sync status")
    
    sync_manager = get_sync_manager()
    status = sync_manager.get_sync_status()
    distribution = sync_manager.get_container_distribution()
    
    return {
        "status": status,
        "distribution": distribution
    }

@router.post("/cluster/sync/migrate")
async def migrate_container(request: ContainerMigrationRequest):
    """Migrate a container from one node to another"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can migrate containers")
    
    cluster_info = await get_cluster_info()
    master_config = read_master_config()
    cluster_key = master_config.get("key")
    
    target_node = None
    for node in cluster_info.nodes:
        if node.id == request.target_node_id:
            target_node = {
                "id": node.id,
                "hostname": node.hostname,
                "ip_address": node.ip_address,
                "port": node.port,
                "status": node.status
            }
            break
    
    if not target_node:
        raise HTTPException(status_code=404, detail="Target node not found")
    
    if target_node["status"] != "online":
        raise HTTPException(status_code=400, detail="Target node is not online")
    
    sync_manager = get_sync_manager()
    success = await sync_manager.migrate_container(
        request.service_name,
        request.source_node_id,
        target_node,
        cluster_key
    )
    
    if success:
        return {
            "message": f"Container {request.service_name} migrated successfully",
            "source_node": request.source_node_id,
            "target_node": request.target_node_id
        }
    else:
        raise HTTPException(status_code=500, detail="Container migration failed")

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

class ReplicationCreate(BaseModel):
    origin_node: str
    destination_node: str
    name: str
    type: str
    sync_schedule: str

def read_replications():
    """Read replication rules from config file"""
    if os.path.exists(REPLICATIONS_FILE):
        try:
            with open(REPLICATIONS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            _clog(f"[REPLICATION] Error reading replications: {e}", error=True)

    return []

def write_replications(replications: list):
    """Write replication rules to config file"""
    ensure_config_dir()
    try:
        with open(REPLICATIONS_FILE, 'w') as f:
            json.dump(replications, f, indent=2)
        _clog(f"[REPLICATION] Saved {len(replications)} replication rules")
    except Exception as e:
        _clog(f"[REPLICATION] Error writing replications: {e}", error=True)

        raise

@router.get("/cluster/replications")
async def get_replications():
    """Get all replication rules"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can manage replications")
    
    replications = read_replications()
    return replications

@router.post("/cluster/replications")
async def create_replication(replication: ReplicationCreate):
    """Create a new replication rule"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can manage replications")
    
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
    
    # TODO: Setup cron job for replication
    _clog(f"[REPLICATION] Created replication: {replication.name} from {replication.origin_node} to {replication.destination_node}")
    
    return new_replication

@router.delete("/cluster/replications/{replication_id}")
async def delete_replication(replication_id: str):
    """Delete a replication rule"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can manage replications")
    
    replications = read_replications()
    
    updated_replications = [r for r in replications if r["id"] != replication_id]
    
    if len(updated_replications) == len(replications):
        raise HTTPException(status_code=404, detail="Replication not found")
    
    write_replications(updated_replications)
    
    # TODO: Remove cron job for this replication
    _clog(f"[REPLICATION] Deleted replication: {replication_id}")
    
    return {"message": "Replication deleted successfully"}

@router.post("/cluster/replications/{replication_id}/trigger")
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
    
    _clog(f"[REPLICATION] Manually triggering replication: {replication['name']} from {replication['origin_node']} to {replication['destination_node']}")
    set_progress(
        "replications",
        replication_id,
        status="running",
        progress=1,
        message="Replication started",
        extra={"replication_id": replication_id, "name": replication["name"]},
    )
    
    import asyncio
    asyncio.create_task(execute_replication(replication))
    
    return {
        "message": "Replication triggered successfully",
        "replication": replication
    }


@router.get("/cluster/replications/{replication_id}/progress")
async def get_replication_progress(replication_id: str):
    """Get latest progress for one replication rule."""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can view replication progress")

    data = get_progress("replications", replication_id)
    if not data:
        return {
            "replication_id": replication_id,
            "status": "idle",
            "progress": 0,
            "message": "No active replication",
            "updated_at": None,
        }
    return {"replication_id": replication_id, **data}

async def execute_replication(replication: dict):
    """Execute the actual replication process"""
    replication_id = replication.get("id", "unknown")

    def _progress(value: int, message: str, status: str = "running"):
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
        
        master_config = read_master_config()
        if not master_config:
            _clog(f"[REPLICATION] No master config found")
            _progress(100, "Master configuration missing", status="failed")
            return
        
        cluster_key = master_config.get("key")
        if not cluster_key:
            _clog(f"[REPLICATION] No cluster key found in config")
            _progress(100, "Cluster key missing", status="failed")
            return
        
        _clog(f"[REPLICATION] Cluster key loaded successfully")
        
        origin_config = read_node_config(origin_node) if origin_node != get_hostname() else None
        dest_config = read_node_config(destination_node) if destination_node != get_hostname() else None
        
        if origin_node == get_hostname():
            origin_ip = "localhost"
            origin_port = 9500
        elif origin_config:
            origin_ip = origin_config['ip_address']
            origin_port = origin_config.get('port', 9500)
        else:
            _clog(f"[REPLICATION] Origin node config not found: {origin_node}")
            _progress(100, f"Origin node not found: {origin_node}", status="failed")
            return
        
        if destination_node == get_hostname():
            dest_ip = "localhost"
            dest_port = 9500
        elif dest_config:
            dest_ip = dest_config['ip_address']
            dest_port = dest_config.get('port', 9500)
        else:
            _clog(f"[REPLICATION] Destination node config not found: {destination_node}")
            _progress(100, f"Destination node not found: {destination_node}", status="failed")
            return
        
        _clog(f"[REPLICATION] Exporting {resource_type} '{resource_name}' from {origin_ip}:{origin_port}")
        _progress(20, "Exporting from origin node")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            export_url = f"http://{origin_ip}:{origin_port}/cluster/export/{resource_type}/{resource_name}"
            _clog(f"[REPLICATION] Export URL: {export_url}")

            export_response = await client.post(
                export_url,
                headers={"Authorization": f"Bearer {cluster_key}"}
            )
            
            _clog(f"[REPLICATION] Export response status: {export_response.status_code}")
            
            if export_response.status_code != 200:
                _clog(f"[REPLICATION] Export failed: {export_response.status_code} - {export_response.text}", error=True)
                _progress(100, "Export failed", status="failed")

                return
            
            export_data = export_response.json()
            export_path = export_data.get("export_path")
            
            if not export_path:
                _clog(f"[REPLICATION] No export path returned")
                _progress(100, "No export path returned", status="failed")
                return
            
            _clog(f"[REPLICATION] Exported to: {export_path}")
            
            download_url = f"http://{origin_ip}:{origin_port}/cluster/download/{export_path.split('/')[-1]}"
            _clog(f"[REPLICATION] Downloading from: {download_url}")
            _progress(45, "Downloading export archive")
            
            download_response = await client.get(
                download_url,
                headers={"Authorization": f"Bearer {cluster_key}"}
            )
            
            if download_response.status_code != 200:
                _clog(f"[REPLICATION] Download failed: {download_response.status_code}", error=True)
                _progress(100, "Download failed", status="failed")

                return
            
            archive_data = download_response.content
            _clog(f"[REPLICATION] Downloaded {len(archive_data)} bytes")
            
            upload_url = f"http://{dest_ip}:{dest_port}/cluster/upload"
            _clog(f"[REPLICATION] Uploading to: {upload_url}")
            _progress(65, "Uploading archive to destination node")
            
            files = {
                "file": (f"{resource_name}.tar.gz", archive_data, "application/gzip")
            }
            
            upload_response = await client.post(
                upload_url,
                headers={"Authorization": f"Bearer {cluster_key}"},
                files=files
            )
            
            if upload_response.status_code != 200:
                _clog(f"[REPLICATION] Upload failed: {upload_response.status_code} - {upload_response.text}", error=True)
                _progress(100, "Upload failed", status="failed")

                return
            
            upload_data = upload_response.json()
            uploaded_path = upload_data.get("path")
            
            _clog(f"[REPLICATION] Uploaded to: {uploaded_path}")
            
            import_url = f"http://{dest_ip}:{dest_port}/cluster/import/{resource_type}"
            _clog(f"[REPLICATION] Importing at: {import_url}")
            _progress(85, "Importing on destination node")
            
            import_params = {
                "archive_path": uploaded_path,
                "name": resource_name
            }
            
            import_response = await client.post(
                import_url,
                headers={"Authorization": f"Bearer {cluster_key}"},
                params=import_params
            )
            
            if import_response.status_code != 200:
                _clog(f"[REPLICATION] Import failed: {import_response.status_code} - {import_response.text}", error=True)
                _progress(100, "Import failed", status="failed")

                return
            
            _clog(f"[REPLICATION] Successfully replicated {resource_type} '{resource_name}' from {origin_node} to {destination_node}")
            _progress(100, "Replication completed successfully", status="completed")
            
    except Exception as e:
        _clog(f"[REPLICATION] Error during replication: {e}", error=True)
        _progress(100, f"Error: {e}", status="failed")

        import traceback
        traceback.print_exc()

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
        node_port = node_config.get('port', 9500)
        
        _clog(f"[REPLICATION] Fetching from {node_ip}:{node_port}")
        
        resources = []
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                containers_url = f"http://{node_ip}:{node_port}/containers"
                _clog(f"[REPLICATION] Fetching containers from: {containers_url}")
                containers_response = await client.get(
                    containers_url,
                    params={"include_compose": "false"},
                    headers={"Authorization": f"Bearer {cluster_key}"}
                )
                
                _clog(f"[REPLICATION] Containers response status: {containers_response.status_code}")
                
                if containers_response.status_code == 200:
                    containers = containers_response.json()
                    _clog(f"[REPLICATION] Found {len(containers)} containers")
                    for container in containers:
                        name = container.get("name")
                        if name and name.strip():
                            resources.append({
                                "name": name,
                                "type": "container"
                            })
                else:
                    _clog(f"[REPLICATION] Failed to fetch containers: {containers_response.text}", error=True)

            except Exception as e:
                _clog(f"[REPLICATION] Error fetching containers: {e}", error=True)

            
            try:
                vms_url = f"http://{node_ip}:{node_port}/vms"
                _clog(f"[REPLICATION] Fetching VMs from: {vms_url}")
                vms_response = await client.get(
                    vms_url,
                    headers={"Authorization": f"Bearer {cluster_key}"}
                )
                
                _clog(f"[REPLICATION] VMs response status: {vms_response.status_code}")
                
                if vms_response.status_code == 200:
                    vms = vms_response.json()
                    _clog(f"[REPLICATION] Found {len(vms)} VMs")
                    for vm in vms:
                        name = vm.get("name")
                        if name and name.strip():
                            resources.append({
                                "name": name,
                                "type": "vm"
                            })
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

@router.post("/cluster/export/{resource_type}/{resource_name}")
async def export_resource(resource_type: str, resource_name: str, authorization: str = Header(None, alias="Authorization")):
    """Export a container or VM with all volumes/storage"""
    _clog(f"[EXPORT] Called with resource_type={resource_type}, resource_name={resource_name}")
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid")
    
    provided_key = authorization[7:]
    master_config = read_master_config()
    child_config = read_child_config()
    
    valid_key = False
    if master_config and master_config.get("key") == provided_key:
        valid_key = True
    elif child_config:
        child_key = child_config.get("cluster_key") or child_config.get("key")
        if child_key == provided_key:
            valid_key = True
    
    if not valid_key:
        raise HTTPException(status_code=401, detail="Invalid cluster key")
    
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
        
    except subprocess.CalledProcessError as e:
        _clog(f"[EXPORT] Command failed: {e.stderr if e.stderr else str(e)}", error=True)

        raise HTTPException(status_code=500, detail=f"Export failed: {e.stderr if e.stderr else str(e)}")
    except Exception as e:
        _clog(f"[EXPORT] Export failed: {e}", error=True)

        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@router.get("/cluster/download/{filename}")
async def download_export(filename: str, authorization: str = Header(None, alias="Authorization")):
    """Download an exported archive"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization")
    
    provided_key = authorization[7:]
    master_config = read_master_config()
    child_config = read_child_config()
    
    valid_key = False
    if master_config and master_config.get("key") == provided_key:
        valid_key = True
    elif child_config:
        child_key = child_config.get("cluster_key") or child_config.get("key")
        if child_key == provided_key:
            valid_key = True
    
    if not valid_key:
        raise HTTPException(status_code=401, detail="Invalid cluster key")
    
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
async def upload_archive(file: UploadFile = File(...), authorization: str = Header(None, alias="Authorization")):
    """Upload an archive for import"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization")
    
    provided_key = authorization[7:]
    master_config = read_master_config()
    child_config = read_child_config()
    
    valid_key = False
    if master_config and master_config.get("key") == provided_key:
        valid_key = True
    elif child_config:
        child_key = child_config.get("cluster_key") or child_config.get("key")
        if child_key == provided_key:
            valid_key = True
    
    if not valid_key:
        raise HTTPException(status_code=401, detail="Invalid cluster key")
    
    try:
        os.makedirs(TEMP_EXPORT_DIR, exist_ok=True)
        
        import uuid
        upload_id = str(uuid.uuid4())
        upload_path = os.path.join(TEMP_EXPORT_DIR, f"{upload_id}_{file.filename}")
        
        _clog(f"[UPLOAD] Receiving file: {file.filename}")
        
        with open(upload_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        _clog(f"[UPLOAD] Saved to: {upload_path} ({len(content)} bytes)")
        
        return {
            "path": upload_path,
            "filename": file.filename
        }
        
    except Exception as e:
        _clog(f"[UPLOAD] Upload failed: {e}", error=True)

        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/cluster/import/{resource_type}")
async def import_resource(resource_type: str, archive_path: str = "", name: str = "", authorization: str = Header(None, alias="Authorization")):
    """Import a container or VM from archive"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization")
    
    provided_key = authorization[7:]
    master_config = read_master_config()
    child_config = read_child_config()
    
    valid_key = False
    if master_config and master_config.get("key") == provided_key:
        valid_key = True
    elif child_config:
        child_key = child_config.get("cluster_key") or child_config.get("key")
        if child_key == provided_key:
            valid_key = True
    
    if not valid_key:
        raise HTTPException(status_code=401, detail="Invalid cluster key")
    
    try:
        if not os.path.exists(archive_path):
            raise HTTPException(status_code=404, detail="Archive not found")
        
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
        
    except subprocess.CalledProcessError as e:
        _clog(f"[IMPORT] Command failed: {e.stderr if e.stderr else str(e)}", error=True)

        raise HTTPException(status_code=500, detail=f"Import failed: {e.stderr if e.stderr else str(e)}")
    except Exception as e:
        _clog(f"[IMPORT] Import failed: {e}", error=True)

        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

