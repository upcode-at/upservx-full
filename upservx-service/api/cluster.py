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
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {cluster_key}"}
            )
            
            if response.status_code == 200:
                metrics = response.json()
                return {
                    "cpu_usage": metrics.get("cpu", {}).get("usage", 0),
                    "memory_usage": metrics.get("memory", {}).get("usage", 0),
                    "disk_usage": metrics.get("storage", {}).get("usage", 0),
                    "success": True
                }
    except (httpx.RequestError, httpx.TimeoutException, Exception):
        pass
    
    return {
        "cpu_usage": 0,
        "memory_usage": 0,
        "disk_usage": 0,
        "success": False
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
        master_node = {
            "id": get_hostname(),
            "hostname": get_hostname(),
            "ip_address": get_local_ip(),
            "port": 9500,
            "status": "online",
            "role": "master",
            "resources": get_system_resources(),
            "last_seen": datetime.now().isoformat()
        }
        nodes.append(master_node)
        
        # Add all child nodes from nodes directory and fetch their metrics
        child_nodes = list_all_nodes()
        for node in child_nodes:
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
        cluster_token = child_config.get("key")
        
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
    if is_master_node():
        raise HTTPException(status_code=400, detail="This node is already a master")
    
    if is_child_node():
        raise HTTPException(status_code=400, detail="Already part of a cluster")
    
    # Prepare node data to register with master
    node_data = {
        "hostname": get_hostname(),
        "ip_address": get_local_ip(),
        "port": 9500,
        "cluster_key": request.token
    }
    
    # Register this node with the master
    try:
        master_url = f"http://{request.master_ip}:{request.port}/cluster/register"
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                master_url,
                json=node_data
            )
            
            if response.status_code != 200:
                error_detail = response.json().get("detail", "Failed to register with master")
                raise HTTPException(status_code=400, detail=f"Master rejected registration: {error_detail}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to master: {str(e)}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="Connection to master timed out")
    
    # Create child configuration
    child_config = {
        "key": request.token,
        "master_ip": request.master_ip,
        "master_port": request.port,
        "joined_at": datetime.now().isoformat()
    }
    
    write_child_config(child_config)
    
    return {
        "message": "Successfully joined cluster",
        "master_ip": request.master_ip
    }

@router.post("/cluster/register")
async def register_node(request: NodeRegistrationRequest):
    """Register a child node with the master (master only)"""
    if not is_master_node():
        raise HTTPException(status_code=403, detail="Only master node can register nodes")
    
    # Verify the cluster key
    master_config = read_master_config()
    if not master_config or master_config.get("key") != request.cluster_key:
        raise HTTPException(status_code=401, detail="Invalid cluster key")
    
    # Check if node already exists
    existing_node = read_node_config(request.hostname)
    if existing_node:
        # Update existing node
        existing_node["ip_address"] = request.ip_address
        existing_node["port"] = request.port
        existing_node["resources"] = get_system_resources()
        existing_node["last_seen"] = datetime.now().isoformat()
        write_node_config(request.hostname, existing_node)
        return {"message": "Node updated successfully", "hostname": request.hostname}
    
    # Create new node configuration
    node_config = {
        "hostname": request.hostname,
        "ip_address": request.ip_address,
        "port": request.port,
        "resources": {},
        "last_seen": datetime.now().isoformat(),
        "registered_at": datetime.now().isoformat()
    }
    
    write_node_config(request.hostname, node_config)
    
    return {
        "message": "Node registered successfully",
        "hostname": request.hostname
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
    
    # Get sync status
    sync_manager = get_sync_manager()
    sync_status = sync_manager.get_sync_status()
    
    # Get active alerts
    metrics_collector = get_metrics_collector()
    alerts = metrics_collector.get_active_alerts()
    critical_alerts = [a for a in alerts if a.get("level") == "critical"]
    warning_alerts = [a for a in alerts if a.get("level") == "warning"]
    
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
            "total_capacity": load_distribution["total_capacity"]
        },
        "sync": sync_status,
        "alerts": {
            "total": len(alerts),
            "critical": len(critical_alerts),
            "warning": len(warning_alerts)
        },
        "timestamp": datetime.now().isoformat()
    }
