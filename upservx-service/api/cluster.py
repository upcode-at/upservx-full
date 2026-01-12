from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import secrets
import socket
import psutil
from datetime import datetime
import json
import os

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
    port: int = 8000

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
    os.makedirs(UPSERVX_CONFIG_DIR, exist_ok=True)
    os.makedirs(NODES_DIR, exist_ok=True)

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

def write_node_config(hostname: str, config: dict):
    """Write node configuration file"""
    ensure_config_dir()
    node_file = os.path.join(NODES_DIR, f"{hostname}.json")
    with open(node_file, 'w') as f:
        json.dump(config, f, indent=2)

def delete_node_config(hostname: str):
    """Delete node configuration file"""
    node_file = os.path.join(NODES_DIR, f"{hostname}.json")
    if os.path.exists(node_file):
        os.remove(node_file)

def list_all_nodes():
    """List all node configurations"""
    nodes = []
    if not os.path.exists(NODES_DIR):
        return nodes
    
    for filename in os.listdir(NODES_DIR):
        if filename.endswith('.json'):
            node_file = os.path.join(NODES_DIR, filename)
            with open(node_file, 'r') as f:
                nodes.append(json.load(f))
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
    return {
        "cpu_usage": psutil.cpu_percent(interval=1),
        "memory_usage": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent
    }

def get_hostname():
    """Get system hostname"""
    return socket.gethostname()

def is_master_node():
    """Check if this node is a master"""
    return os.path.exists(MASTER_CONFIG_FILE)

def is_child_node():
    """Check if this node is a child"""
    return os.path.exists(CHILD_CONFIG_FILE)

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
        master_node = {
            "id": get_hostname(),
            "hostname": get_hostname(),
            "ip_address": get_local_ip(),
            "port": 8000,
            "status": "online",
            "role": "master",
            "resources": get_system_resources(),
            "last_seen": datetime.now().isoformat()
        }
        nodes.append(master_node)
        
        # Add all child nodes from nodes directory
        child_nodes = list_all_nodes()
        for node in child_nodes:
            if node.get("hostname") != get_hostname():
                nodes.append({
                    "id": node.get("hostname"),
                    "hostname": node.get("hostname"),
                    "ip_address": node.get("ip_address"),
                    "port": node.get("port", 8000),
                    "status": "online",  # TODO: Implement health check
                    "role": "child",
                    "resources": node.get("resources", {}),
                    "last_seen": node.get("last_seen", "")
                })
    
    elif is_child:
        child_config = read_child_config()
        master_ip = child_config.get("master_ip")
        cluster_token = child_config.get("key")
        
        # Add self as child node
        child_node = {
            "id": get_hostname(),
            "hostname": get_hostname(),
            "ip_address": get_local_ip(),
            "port": 8000,
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
        "port": 8000,
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
    if is_master_node():
        raise HTTPException(status_code=400, detail="This node is already a master")
    
    if is_child_node():
        raise HTTPException(status_code=400, detail="Already part of a cluster")
    
    # Create child configuration
    child_config = {
        "key": request.token,
        "master_ip": request.master_ip,
        "master_port": request.port,
        "joined_at": datetime.now().isoformat()
    }
    
    write_child_config(child_config)
    
    # TODO: Register this node with master via API call
    # For now, the master needs to be notified manually or via periodic heartbeat
    
    return {
        "message": "Successfully joined cluster",
        "master_ip": request.master_ip
    }

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
