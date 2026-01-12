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

# Path to store cluster configuration
CLUSTER_CONFIG_FILE = "/opt/upservx/cluster_config.json"

class ClusterCreateRequest(BaseModel):
    cluster_name: str

class ClusterJoinRequest(BaseModel):
    master_ip: str
    token: str

class ClusterNode(BaseModel):
    id: str
    hostname: str
    ip_address: str
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

def get_cluster_config():
    """Load cluster configuration from file"""
    if os.path.exists(CLUSTER_CONFIG_FILE):
        with open(CLUSTER_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "is_master": False,
        "is_member": False,
        "master_ip": None,
        "cluster_token": None,
        "cluster_name": None,
        "nodes": []
    }

def save_cluster_config(config: dict):
    """Save cluster configuration to file"""
    os.makedirs(os.path.dirname(CLUSTER_CONFIG_FILE), exist_ok=True)
    with open(CLUSTER_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

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

@router.get("/cluster/info")
async def get_cluster_info():
    """Get cluster information"""
    config = get_cluster_config()
    
    nodes = []
    if config["is_member"]:
        # Add local node
        local_node = {
            "id": get_hostname(),
            "hostname": get_hostname(),
            "ip_address": get_local_ip(),
            "status": "online",
            "role": "master" if config["is_master"] else "child",
            "resources": get_system_resources(),
            "last_seen": datetime.now().isoformat()
        }
        nodes.append(local_node)
        
        # Add other nodes from config
        for node in config.get("nodes", []):
            if node["id"] != get_hostname():
                nodes.append(node)
    
    return ClusterInfo(
        is_master=config["is_master"],
        is_member=config["is_member"],
        master_ip=config.get("master_ip"),
        cluster_token=config.get("cluster_token"),
        nodes=nodes
    )

@router.post("/cluster/create")
async def create_cluster(request: ClusterCreateRequest):
    """Create a new cluster and become master node"""
    config = get_cluster_config()
    
    if config["is_member"]:
        raise HTTPException(status_code=400, detail="Already part of a cluster")
    
    # Generate cluster token
    token = secrets.token_urlsafe(32)
    
    # Update configuration
    config["is_master"] = True
    config["is_member"] = True
    config["cluster_name"] = request.cluster_name
    config["cluster_token"] = token
    config["master_ip"] = get_local_ip()
    config["nodes"] = [{
        "id": get_hostname(),
        "hostname": get_hostname(),
        "ip_address": get_local_ip(),
        "status": "online",
        "role": "master",
        "resources": get_system_resources(),
        "last_seen": datetime.now().isoformat()
    }]
    
    save_cluster_config(config)
    
    return {
        "message": "Cluster created successfully",
        "token": token,
        "master_ip": get_local_ip()
    }

@router.post("/cluster/join")
async def join_cluster(request: ClusterJoinRequest):
    """Join an existing cluster as child node"""
    config = get_cluster_config()
    
    if config["is_member"]:
        raise HTTPException(status_code=400, detail="Already part of a cluster")
    
    # TODO: Verify token with master node via API call
    # For now, we'll just trust the token
    
    # Update configuration
    config["is_master"] = False
    config["is_member"] = True
    config["master_ip"] = request.master_ip
    config["cluster_token"] = request.token
    config["nodes"] = []
    
    save_cluster_config(config)
    
    # TODO: Register this node with master
    
    return {
        "message": "Successfully joined cluster",
        "master_ip": request.master_ip
    }

@router.post("/cluster/leave")
async def leave_cluster():
    """Leave the current cluster"""
    config = get_cluster_config()
    
    if not config["is_member"]:
        raise HTTPException(status_code=400, detail="Not part of any cluster")
    
    if config["is_master"]:
        # TODO: Notify all child nodes
        pass
    else:
        # TODO: Notify master node
        pass
    
    # Reset configuration
    config["is_master"] = False
    config["is_member"] = False
    config["master_ip"] = None
    config["cluster_token"] = None
    config["cluster_name"] = None
    config["nodes"] = []
    
    save_cluster_config(config)
    
    return {"message": "Successfully left cluster"}

@router.delete("/cluster/nodes/{node_id}")
async def remove_node(node_id: str):
    """Remove a node from the cluster (master only)"""
    config = get_cluster_config()
    
    if not config["is_master"]:
        raise HTTPException(status_code=403, detail="Only master node can remove nodes")
    
    # Remove node from configuration
    config["nodes"] = [n for n in config["nodes"] if n["id"] != node_id]
    save_cluster_config(config)
    
    # TODO: Notify the removed node
    
    return {"message": f"Node {node_id} removed successfully"}

@router.post("/cluster/sync")
async def sync_cluster():
    """Sync cluster state (called by master to update child nodes)"""
    # TODO: Implement cluster synchronization
    return {"message": "Cluster synchronized"}

@router.get("/cluster/nodes")
async def get_cluster_nodes():
    """Get all nodes in the cluster"""
    config = get_cluster_config()
    
    if not config["is_member"]:
        raise HTTPException(status_code=400, detail="Not part of any cluster")
    
    return {"nodes": config.get("nodes", [])}
