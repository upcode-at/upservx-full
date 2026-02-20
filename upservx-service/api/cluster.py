from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import secrets
import socket
import psutil
from datetime import datetime
import json
import os
import httpx
from load_balancer import get_load_balancer, LoadBalancingStrategy
from container_sync import get_sync_manager, SyncRule, SyncStrategy
from metrics_collector import get_metrics_collector

router = APIRouter()

# Paths for cluster configuration
UPSERVX_CONFIG_DIR = "/etc/upservx"
MASTER_CONFIG_FILE = os.path.join(UPSERVX_CONFIG_DIR, "master")
CHILD_CONFIG_FILE = os.path.join(UPSERVX_CONFIG_DIR, "child")
NODES_DIR = os.path.join(UPSERVX_CONFIG_DIR, "nodes")

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
        print(f"[CLUSTER] Config directories ensured: {UPSERVX_CONFIG_DIR}, {NODES_DIR}")
        print(f"[CLUSTER] NODES_DIR exists: {os.path.exists(NODES_DIR)}")
        print(f"[CLUSTER] NODES_DIR is writable: {os.access(NODES_DIR, os.W_OK)}")
    except Exception as e:
        print(f"[CLUSTER] ERROR creating config directories: {e}")
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
        print(f"[CLUSTER] Hostname {base_hostname} exists, trying {hostname}")
    
    return hostname

def write_node_config(hostname: str, config: dict):
    """Write node configuration file"""
    ensure_config_dir()
    node_file = os.path.join(NODES_DIR, f"{hostname}.json")
    print(f"[CLUSTER] Writing node config to {node_file}")
    try:
        with open(node_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"[CLUSTER] Successfully wrote node config for {hostname}")
        # Verify it was written
        if os.path.exists(node_file):
            print(f"[CLUSTER] File {node_file} exists and has {os.path.getsize(node_file)} bytes")
        else:
            print(f"[CLUSTER] WARNING: File {node_file} does not exist after write!")
    except Exception as e:
        print(f"[CLUSTER] ERROR writing node config: {e}")
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
        print(f"[CLUSTER] NODES_DIR does not exist: {NODES_DIR}")
        return nodes
    
    print(f"[CLUSTER] Listing nodes from {NODES_DIR}")
    try:
        files = os.listdir(NODES_DIR)
        print(f"[CLUSTER] Found {len(files)} files in NODES_DIR: {files}")
        
        for filename in files:
            if filename.endswith('.json'):
                node_file = os.path.join(NODES_DIR, filename)
                print(f"[CLUSTER] Reading node config: {node_file}")
                try:
                    with open(node_file, 'r') as f:
                        node_data = json.load(f)
                        nodes.append(node_data)
                        print(f"[CLUSTER] Loaded node: {node_data.get('hostname', 'unknown')}")
                except Exception as e:
                    print(f"[CLUSTER] ERROR reading {node_file}: {e}")
    except Exception as e:
        print(f"[CLUSTER] ERROR listing nodes: {e}")
    
    print(f"[CLUSTER] Total nodes loaded: {len(nodes)}")
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
    
    # Get container counts
    try:
        from compose_manager import ComposeManager
        compose_manager = ComposeManager()
        running_containers = 0
        total_containers = 0
        
        for service in compose_manager.list_services():
            total_containers += 1
            if service.get("status") == "running":
                running_containers += 1
        
        print(f"[RESOURCES] Containers: {running_containers}/{total_containers}")
    except Exception as e:
        print(f"[RESOURCES] Error counting containers: {e}")
        import traceback
        traceback.print_exc()
        running_containers = 0
        total_containers = 0
    
    # Get VM counts
    try:
        from vms import list_vms_with_status
        vms = list_vms_with_status()
        running_vms = sum(1 for vm in vms if vm.status == "running")
        total_vms = len(vms)
        print(f"[RESOURCES] VMs: {running_vms}/{total_vms}")
    except Exception as e:
        print(f"[RESOURCES] Error counting VMs: {e}")
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
    
    print(f"[RESOURCES] Returning: containers={total_containers}/{running_containers}, vms={total_vms}/{running_vms}")
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
            return child_config.get("key")
    return None

async def fetch_node_metrics(ip_address: str, port: int, cluster_key: str):
    """Fetch metrics from a child node"""
    try:
        url = f"http://{ip_address}:{port}/metrics"
        print(f"[CLUSTER] Fetching metrics from {url}")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {cluster_key}"}
            )
            
            if response.status_code == 200:
                metrics = response.json()
                print(f"[CLUSTER] Successfully fetched metrics from {ip_address}")
                print(f"[CLUSTER] Raw metrics response: {json.dumps(metrics, indent=2)}")
                
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
                print(f"[CLUSTER] Extracted values: cpu_count={extracted['cpu_count']}, memory_total={extracted['memory_total']}")
                return extracted
            else:
                print(f"[CLUSTER] Failed to fetch metrics from {ip_address}: HTTP {response.status_code}")
    except (httpx.RequestError, httpx.TimeoutException, Exception) as e:
        print(f"[CLUSTER] Error fetching metrics from {ip_address}: {e}")
    
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

@router.get("/metrics")
async def get_node_metrics():
    """Get current node metrics (for cluster communication)"""
    # Get container counts
    try:
        from compose_manager import ComposeManager
        compose_manager = ComposeManager()
        running_containers = 0
        total_containers = 0
        
        for service in compose_manager.list_services():
            total_containers += 1
            if service.get("status") == "running":
                running_containers += 1
        
        print(f"[METRICS] Containers: {running_containers}/{total_containers}")
    except Exception as e:
        print(f"[METRICS] Error counting containers: {e}")
        import traceback
        traceback.print_exc()
        running_containers = 0
        total_containers = 0
    
    # Get VM counts
    try:
        from vms import list_vms_with_status
        vms = list_vms_with_status()
        running_vms = sum(1 for vm in vms if vm.status == "running")
        total_vms = len(vms)
        print(f"[METRICS] VMs: {running_vms}/{total_vms}")
    except Exception as e:
        print(f"[METRICS] Error counting VMs: {e}")
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
    
    print(f"[METRICS] Returning metrics with containers={total_containers}/{running_containers}, vms={total_vms}/{running_vms}")
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
        # Read all node configs
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
        
        # Try to read it back
        with open(test_file, 'r') as f:
            read_data = json.load(f)
        
        # Clean up
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
        
        # Add master node
        master_resources = get_system_resources()
        print(f"[CLUSTER] Master node resources: {json.dumps(master_resources, indent=2)}")
        
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
        
        print(f"[CLUSTER] Master node added with containers: {master_resources.get('total_containers')}/{master_resources.get('running_containers')}, vms: {master_resources.get('total_vms')}/{master_resources.get('running_vms')}")
        
        # Add all child nodes from nodes directory and fetch their metrics
        child_nodes = list_all_nodes()
        print(f"[CLUSTER] Master node found {len(child_nodes)} nodes in directory")
        for node in child_nodes:
            print(f"[CLUSTER] Processing node: {node.get('hostname')}")
            if node.get("hostname") != get_hostname():
                # Fetch current metrics from child node
                resources = await fetch_node_metrics(
                    node.get("ip_address"),
                    node.get("port", 9500),
                    cluster_token
                )
                
                # Update node config with fresh metrics
                node["resources"] = resources
                node["last_seen"] = datetime.now().isoformat()
                write_node_config(node.get("hostname"), node)
                
                # Remove success flag before adding to response
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
        
        print(f"[CLUSTER] Child node trying to fetch master info from {master_ip}:{master_port}")
        
        # Try to fetch master node info
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"http://{master_ip}:{master_port}/metrics",
                    headers={"Authorization": f"Bearer {cluster_token}"}
                )
                if response.status_code == 200:
                    master_metrics = response.json()
                    print(f"[CLUSTER] Successfully fetched master metrics")
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
                    print(f"[CLUSTER] Failed to fetch master metrics: HTTP {response.status_code}")
                    raise Exception("Master unreachable")
        except Exception as e:
            # Master unreachable, show as offline
            print(f"[CLUSTER] Master unreachable: {e}")
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
        
        # Add self as child node
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
    
    # Generate cluster key
    cluster_key = secrets.token_urlsafe(32)
    
    # Create master configuration
    master_config = {
        "key": cluster_key,
        "cluster_name": request.cluster_name,
        "created_at": datetime.now().isoformat()
    }
    
    write_master_config(master_config)
    
    # Create master node config in nodes directory
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
    print(f"[CLUSTER] ========================================")
    print(f"[CLUSTER] JOIN REQUEST INITIATED")
    print(f"[CLUSTER] Target Master: {request.master_ip}:{request.port}")
    print(f"[CLUSTER] Token: {request.token[:15]}...")
    
    if is_master_node():
        print(f"[CLUSTER] ERROR: This node is already a master")
        raise HTTPException(status_code=400, detail="This node is already a master")
    
    if is_child_node():
        print(f"[CLUSTER] ERROR: Already part of a cluster")
        raise HTTPException(status_code=400, detail="Already part of a cluster")
    
    my_hostname = get_hostname()
    my_ip = get_local_ip()
    
    print(f"[CLUSTER] My hostname: {my_hostname}")
    print(f"[CLUSTER] My IP: {my_ip}")
    
    # Prepare node data to register with master
    my_resources = get_system_resources()
    node_data = {
        "hostname": my_hostname,
        "ip_address": my_ip,
        "port": 9500,
        "cluster_key": request.token,
        "resources": my_resources
    }
    
    print(f"[CLUSTER] Node data prepared: {node_data}")
    print(f"[CLUSTER] Attempting registration with master...")
    
    # Register this node with the master
    try:
        master_url = f"http://{request.master_ip}:{request.port}/cluster/register"
        print(f"[CLUSTER] POST {master_url}")
        print(f"[CLUSTER] Payload: {json.dumps(node_data, indent=2)}")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                master_url,
                json=node_data
            )
            
            print(f"[CLUSTER] Response status: {response.status_code}")
            print(f"[CLUSTER] Response body: {response.text}")
            
            if response.status_code != 200:
                try:
                    error_detail = response.json().get("detail", "Failed to register with master")
                except:
                    error_detail = response.text
                print(f"[CLUSTER] Registration FAILED: {error_detail}")
                raise HTTPException(status_code=400, detail=f"Master rejected registration: {error_detail}")
            
            response_data = response.json()
            assigned_hostname = response_data.get("hostname", my_hostname)
            
            print(f"[CLUSTER] Registration SUCCESSFUL")
            print(f"[CLUSTER] Assigned hostname: {assigned_hostname}")
            
    except HTTPException:
        raise
    except httpx.RequestError as e:
        print(f"[CLUSTER] Connection error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to connect to master: {str(e)}")
    except httpx.TimeoutException:
        print(f"[CLUSTER] Connection timeout to {request.master_ip}:{request.port}")
        raise HTTPException(status_code=400, detail="Connection to master timed out")
    except Exception as e:
        print(f"[CLUSTER] Unexpected error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error during registration: {str(e)}")
    
    # Create child configuration
    child_config = {
        "key": request.token,
        "master_ip": request.master_ip,
        "master_port": request.port,
        "joined_at": datetime.now().isoformat(),
        "assigned_hostname": assigned_hostname
    }
    
    print(f"[CLUSTER] Writing child configuration...")
    write_child_config(child_config)
    print(f"[CLUSTER] Child configuration written to {CHILD_CONFIG_FILE}")
    print(f"[CLUSTER] JOIN COMPLETED SUCCESSFULLY")
    print(f"[CLUSTER] ========================================")
    
    return {
        "message": "Successfully joined cluster",
        "master_ip": request.master_ip,
        "assigned_hostname": assigned_hostname
    }

@router.post("/cluster/register")
async def register_node(request: NodeRegistrationRequest):
    """Register a child node with the master (master only)"""
    print(f"[CLUSTER] ========================================")
    print(f"[CLUSTER] Registration request from {request.hostname} ({request.ip_address}:{request.port})")
    print(f"[CLUSTER] Cluster key provided: {request.cluster_key[:10]}...")
    
    if not is_master_node():
        print(f"[CLUSTER] ERROR: This node is not a master")
        raise HTTPException(status_code=403, detail="Only master node can register nodes")
    
    print(f"[CLUSTER] This is a master node, proceeding...")
    
    # Verify the cluster key
    master_config = read_master_config()
    if not master_config:
        print(f"[CLUSTER] ERROR: Master config not found")
        raise HTTPException(status_code=500, detail="Master configuration not found")
    
    expected_key = master_config.get("key")
    print(f"[CLUSTER] Expected key: {expected_key[:10]}...")
    
    if expected_key != request.cluster_key:
        print(f"[CLUSTER] ERROR: Invalid cluster key from {request.hostname}")
        raise HTTPException(status_code=401, detail="Invalid cluster key")
    
    print(f"[CLUSTER] Cluster key verified successfully")
    
    # Check if this is the same node (same IP) updating itself
    original_hostname = request.hostname
    all_nodes = list_all_nodes()
    
    # Check if a node with this IP already exists
    same_ip_node = None
    for node in all_nodes:
        if node.get("ip_address") == request.ip_address:
            same_ip_node = node
            break
    
    if same_ip_node:
        # Same IP, just update the existing entry
        existing_hostname = same_ip_node.get("hostname")
        print(f"[CLUSTER] Node with IP {request.ip_address} already exists as {existing_hostname}, updating...")
        same_ip_node["hostname"] = existing_hostname  # Keep the original hostname
        same_ip_node["ip_address"] = request.ip_address
        same_ip_node["port"] = request.port
        same_ip_node["resources"] = request.resources
        same_ip_node["last_seen"] = datetime.now().isoformat()
        try:
            write_node_config(existing_hostname, same_ip_node)
            print(f"[CLUSTER] Node {existing_hostname} updated successfully")
            return {"message": "Node updated successfully", "hostname": existing_hostname}
        except Exception as e:
            print(f"[CLUSTER] ERROR updating node: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update node: {str(e)}")
    
    # Find a unique hostname (append -2, -3, etc. if needed)
    unique_hostname = find_unique_hostname(original_hostname)
    
    if unique_hostname != original_hostname:
        print(f"[CLUSTER] Hostname {original_hostname} already exists, using {unique_hostname} instead")
    
    # Create new node configuration
    print(f"[CLUSTER] Creating new node config for {unique_hostname}")
    node_config = {
        "hostname": unique_hostname,
        "original_hostname": original_hostname,
        "ip_address": request.ip_address,
        "port": request.port,
        "resources": request.resources,
        "last_seen": datetime.now().isoformat(),
        "registered_at": datetime.now().isoformat()
    }
    
    print(f"[CLUSTER] Node config: {node_config}")
    
    try:
        write_node_config(unique_hostname, node_config)
        print(f"[CLUSTER] Node {unique_hostname} registered successfully")
        print(f"[CLUSTER] ========================================")
        
        # Verify registration
        verification = read_node_config(unique_hostname)
        if verification:
            print(f"[CLUSTER] Verification: Node config readable after write")
        else:
            print(f"[CLUSTER] WARNING: Node config not readable after write!")
        
        return {
            "message": "Node registered successfully",
            "hostname": unique_hostname,
            "original_hostname": original_hostname if unique_hostname != original_hostname else None
        }
    except Exception as e:
        print(f"[CLUSTER] ERROR registering node: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to register node: {str(e)}")

@router.post("/cluster/leave")
async def leave_cluster():
    """Leave the current cluster"""
    if not is_master_node() and not is_child_node():
        raise HTTPException(status_code=400, detail="Not part of any cluster")
    
    if is_master_node():
        # Remove master configuration
        if os.path.exists(MASTER_CONFIG_FILE):
            os.remove(MASTER_CONFIG_FILE)
        
        # Remove all node configurations
        if os.path.exists(NODES_DIR):
            for filename in os.listdir(NODES_DIR):
                node_file = os.path.join(NODES_DIR, filename)
                if os.path.isfile(node_file):
                    os.remove(node_file)
        
        # TODO: Notify all child nodes
        
    elif is_child_node():
        # Remove child configuration
        if os.path.exists(CHILD_CONFIG_FILE):
            os.remove(CHILD_CONFIG_FILE)
        
        # TODO: Notify master node
    
    return {"message": "Successfully left cluster"}

@router.delete("/cluster/nodes/{node_id}")
async def remove_node(node_id: str):
    """Remove a node from the cluster (master only)"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can remove nodes")
    
    # Remove node configuration
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
    
    # Get cluster info
    cluster_info = await get_cluster_info()
    nodes = cluster_info.nodes
    
    # Get load balancer and select node
    lb = get_load_balancer()
    
    try:
        strategy = LoadBalancingStrategy(request.strategy)
    except ValueError:
        strategy = LoadBalancingStrategy.LEAST_LOADED
    
    # Convert ClusterNode objects to dicts
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
    
    # Get cluster info
    cluster_info = await get_cluster_info()
    
    # Convert ClusterNode objects to dicts
    nodes_dict = [
        {
            "id": n.id,
            "hostname": n.hostname,
            "status": n.status,
            "resources": n.resources
        }
        for n in cluster_info.nodes
    ]
    
    # Get load balancer and calculate distribution
    lb = get_load_balancer()
    distribution = lb.get_cluster_load_distribution(nodes_dict)
    
    return distribution

@router.get("/cluster/load/recommendations")
async def get_rebalancing_recommendations():
    """Get recommendations for workload rebalancing"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can get rebalancing recommendations")
    
    # Get cluster info
    cluster_info = await get_cluster_info()
    
    # Convert ClusterNode objects to dicts
    nodes_dict = [
        {
            "id": n.id,
            "hostname": n.hostname,
            "status": n.status,
            "resources": n.resources
        }
        for n in cluster_info.nodes
    ]
    
    # Get load balancer and recommendations
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
    
    # Get cluster info  
    cluster_info = await get_cluster_info()
    master_config = read_master_config()
    cluster_key = master_config.get("key")
    
    # Convert ClusterNode objects to dicts
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
    
    # Execute sync
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
    
    # Get cluster info
    cluster_info = await get_cluster_info()
    master_config = read_master_config()
    cluster_key = master_config.get("key")
    
    # Find target node
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
    
    # Execute migration
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
    
    # Get cluster info
    cluster_info = await get_cluster_info()
    
    # Convert ClusterNode objects to dicts
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
    
    # Get cluster info
    cluster_info = await get_cluster_info()
    
    # Convert ClusterNode objects to dicts
    nodes_dict = [
        {
            "id": n.id,
            "hostname": n.hostname,
            "status": n.status,
            "resources": n.resources
        }
        for n in cluster_info.nodes
    ]
    
    # Calculate health metrics
    total_nodes = len(nodes_dict)
    online_nodes = sum(1 for n in nodes_dict if n["status"] == "online")
    offline_nodes = total_nodes - online_nodes
    
    # Get load balancer stats
    lb = get_load_balancer()
    load_distribution = lb.get_cluster_load_distribution(nodes_dict)
    
    # Calculate total containers and VMs across all nodes
    total_running_containers = 0
    total_synced_containers = 0
    total_running_vms = 0
    total_vms = 0
    
    for node in nodes_dict:
        if node.get("status") == "online":
            resources = node.get("resources", {})
            total_running_containers += resources.get("running_containers", 0)
            total_synced_containers += resources.get("total_containers", 0)
            total_running_vms += resources.get("running_vms", 0)
            total_vms += resources.get("total_vms", 0)
    
    # Get sync status (rules count)
    sync_manager = get_sync_manager()
    sync_rules_count = len(sync_manager.sync_rules)
    
    sync_status = {
        "total_synced_containers": total_synced_containers,
        "running_containers": total_running_containers,
        "total_vms": total_vms,
        "running_vms": total_running_vms,
        "sync_rules_count": sync_rules_count
    }
    
    # Get active alerts
    metrics_collector = get_metrics_collector()
    alerts = metrics_collector.get_active_alerts()
    critical_alerts = [a for a in alerts if a.get("level") == "critical"]
    warning_alerts = [a for a in alerts if a.get("level") == "warning"]
    
    # Calculate total cores and RAM across cluster
    total_cpu_cores = 0
    total_memory_gb = 0.0
    
    print(f"[CLUSTER] ========== HEALTH CALCULATION ==========")
    print(f"[CLUSTER] Total nodes: {len(nodes_dict)}")
    
    for node in nodes_dict:
        resources = node.get("resources", {})
        node_cores = resources.get("cpu_count", 0)
        node_memory_bytes = resources.get("memory_total", 0)
        node_memory_gb = node_memory_bytes / (1024**3)
        
        print(f"[CLUSTER] Node: {node.get('hostname')}")
        print(f"[CLUSTER]   - Status: {node.get('status')}")
        print(f"[CLUSTER]   - CPU Cores: {node_cores}")
        print(f"[CLUSTER]   - Memory: {node_memory_gb:.2f} GB")
        print(f"[CLUSTER]   - Resources: {resources}")
        
        total_cpu_cores += node_cores
        total_memory_gb += node_memory_gb
    
    print(f"[CLUSTER] TOTALS:")
    print(f"[CLUSTER]   - Total CPU Cores: {total_cpu_cores}")
    print(f"[CLUSTER]   - Total Memory: {total_memory_gb:.2f} GB")
    print(f"[CLUSTER] ==========================================")

    
    # Determine overall health
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
        "sync": sync_status,
        "alerts": {
            "total": len(alerts),
            "critical": len(critical_alerts),
            "warning": len(warning_alerts)
        },
        "timestamp": datetime.now().isoformat()
    }
