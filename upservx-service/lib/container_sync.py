"""
Container Synchronization Module for UpservX Cluster Management

Handles container state synchronization across cluster nodes.
"""

from typing import List, Dict, Optional, Set
from datetime import datetime
import asyncio
import json
import os
from handlers.compose_manager import ComposeManager
from lib.cluster_security import (
    bootstrap_peer_ca,
    cluster_url,
    normalize_cluster_port,
    signed_cluster_request,
)
from lib.load_balancer import get_load_balancer, LoadBalancingStrategy

UPSERVX_CONFIG_DIR = "/etc/upservx"
SYNC_STATE_FILE = os.path.join(UPSERVX_CONFIG_DIR, "sync_state.json")
SYNC_RULES_FILE = os.path.join(UPSERVX_CONFIG_DIR, "sync_rules.json")

class SyncStrategy:
    """Container synchronization strategies"""
    REPLICATE = "replicate"  # Replicate on all nodes
    DISTRIBUTE = "distribute"  # Distribute across nodes
    ACTIVE_PASSIVE = "active_passive"  # Active on one, passive on others
    CUSTOM = "custom"  # Custom rules

class ContainerState:
    """Represents the state of a container"""
    
    def __init__(self, service_id: str, service_name: str, status: str, 
                 node_id: str, config: Dict):
        self.service_id = service_id
        self.service_name = service_name
        self.status = status  # running, stopped, error
        self.node_id = node_id
        self.config = config
        self.last_updated = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "status": self.status,
            "node_id": self.node_id,
            "config": self.config,
            "last_updated": self.last_updated
        }

class SyncRule:
    """Synchronization rule for a service"""
    
    def __init__(self, service_name: str, strategy: str, 
                 target_nodes: Optional[List[str]] = None,
                 replica_count: int = 1):
        self.service_name = service_name
        self.strategy = strategy
        self.target_nodes = target_nodes or []
        self.replica_count = replica_count
    
    def to_dict(self) -> Dict:
        return {
            "service_name": self.service_name,
            "strategy": self.strategy,
            "target_nodes": self.target_nodes,
            "replica_count": self.replica_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SyncRule":
        return cls(
            service_name=data.get("service_name"),
            strategy=data.get("strategy", SyncStrategy.DISTRIBUTE),
            target_nodes=data.get("target_nodes", []),
            replica_count=data.get("replica_count", 1)
        )

class ContainerSyncManager:
    """Manages container synchronization across cluster"""
    
    def __init__(self):
        self.sync_rules: Dict[str, SyncRule] = {}
        self.container_states: Dict[str, ContainerState] = {}
        self.load_sync_rules()
        self.load_sync_state()
    
    def load_sync_rules(self):
        """Load synchronization rules from file"""
        if os.path.exists(SYNC_RULES_FILE):
            try:
                with open(SYNC_RULES_FILE, 'r') as f:
                    data = json.load(f)
                    self.sync_rules = {
                        name: SyncRule.from_dict(rule)
                        for name, rule in data.items()
                    }
            except Exception as e:
                print(f"Error loading sync rules: {e}")
    
    def save_sync_rules(self):
        """Save synchronization rules to file"""
        os.makedirs(UPSERVX_CONFIG_DIR, exist_ok=True)
        try:
            with open(SYNC_RULES_FILE, 'w') as f:
                data = {
                    name: rule.to_dict()
                    for name, rule in self.sync_rules.items()
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving sync rules: {e}")
    
    def load_sync_state(self):
        """Load container synchronization state"""
        if os.path.exists(SYNC_STATE_FILE):
            try:
                with open(SYNC_STATE_FILE, 'r') as f:
                    data = json.load(f)
                    for key, state_data in data.items():
                        self.container_states[key] = ContainerState(
                            service_id=state_data["service_id"],
                            service_name=state_data["service_name"],
                            status=state_data["status"],
                            node_id=state_data["node_id"],
                            config=state_data["config"]
                        )
            except Exception as e:
                print(f"Error loading sync state: {e}")
    
    def save_sync_state(self):
        """Save container synchronization state"""
        os.makedirs(UPSERVX_CONFIG_DIR, exist_ok=True)
        try:
            with open(SYNC_STATE_FILE, 'w') as f:
                data = {
                    key: state.to_dict()
                    for key, state in self.container_states.items()
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving sync state: {e}")
    
    def add_sync_rule(self, rule: SyncRule):
        """Add or update a synchronization rule"""
        self.sync_rules[rule.service_name] = rule
        self.save_sync_rules()
    
    def remove_sync_rule(self, service_name: str):
        """Remove a synchronization rule"""
        if service_name in self.sync_rules:
            del self.sync_rules[service_name]
            self.save_sync_rules()
    
    def get_sync_rule(self, service_name: str) -> Optional[SyncRule]:
        """Get synchronization rule for a service"""
        return self.sync_rules.get(service_name)
    
    async def sync_container_to_node(self, service_name: str, target_node: Dict,
                                     cluster_key: str) -> bool:
        """
        Synchronize a container to a target node
        
        Args:
            service_name: Name of the service to sync
            target_node: Target node information
            cluster_key: Cluster authentication key
        
        Returns:
            True if sync successful, False otherwise
        """
        try:
            service_config = await self._get_service_config(service_name)
            
            if not service_config:
                return False
            
            port = normalize_cluster_port(target_node.get("port"))
            ca_certificate = target_node.get("tls_ca_certificate")
            if not ca_certificate:
                ca_certificate, authenticated_node_id, port = await bootstrap_peer_ca(
                    target_node["ip_address"],
                    port,
                    cluster_key,
                    expected_node_id=target_node.get("hostname"),
                )
                target_node["tls_ca_certificate"] = ca_certificate
                target_node["port"] = port
                from api.cluster import write_node_config

                write_node_config(
                    str(target_node.get("hostname") or authenticated_node_id),
                    target_node,
                )

            response = await signed_cluster_request(
                "POST",
                cluster_url(
                    target_node["ip_address"],
                    port,
                    "/containers/deploy",
                ),
                key=cluster_key,
                ca_certificate=ca_certificate,
                json_data={
                    "service_name": service_name,
                    "config": service_config,
                },
                timeout=30.0,
            )

            if response.status_code == 200:
                state_key = f"{service_name}_{target_node['id']}"
                self.container_states[state_key] = ContainerState(
                    service_id=state_key,
                    service_name=service_name,
                    status="running",
                    node_id=target_node['id'],
                    config=service_config
                )
                self.save_sync_state()
                return True

        except Exception as e:
            print(f"Error syncing container to node: {e}")
        
        return False
    
    async def _get_service_config(self, service_name: str) -> Optional[Dict]:
        """Get service configuration"""
        # This is a placeholder - would need actual implementation
        # to read docker-compose files or app store configs
        try:
            compose_manager = ComposeManager()
            projects = compose_manager.list_projects()
            
            for project in projects:
                for service in project.get("services", []):
                    if service.get("name") == service_name or f"{project['name']}_{service.get('name')}" == service_name:
                        return {
                            "name": service_name,
                            "image": service.get("image", ""),
                            "environment": service.get("environment", {}),
                            "volumes": service.get("volumes", []),
                            "ports": service.get("ports", [])
                        }
        except Exception as e:
            print(f"Error getting service config: {e}")
        
        return None
    
    async def sync_all_containers(self, nodes: List[Dict], cluster_key: str):
        """
        Synchronize all containers according to sync rules
        
        Args:
            nodes: List of available cluster nodes
            cluster_key: Cluster authentication key
        """
        for service_name, rule in self.sync_rules.items():
            await self._sync_service_by_rule(service_name, rule, nodes, cluster_key)
    
    async def _sync_service_by_rule(self, service_name: str, rule: SyncRule,
                                    nodes: List[Dict], cluster_key: str):
        """Synchronize a service according to its rule"""
        online_nodes = [n for n in nodes if n.get("status") == "online"]
        
        if rule.strategy == SyncStrategy.REPLICATE:
            for node in online_nodes:
                await self.sync_container_to_node(service_name, node, cluster_key)
        
        elif rule.strategy == SyncStrategy.DISTRIBUTE:
            lb = get_load_balancer()
            for i in range(rule.replica_count):
                selected_node = lb.select_node(
                    online_nodes,
                    strategy=LoadBalancingStrategy.LEAST_LOADED,
                    service_id=f"{service_name}_replica_{i}"
                )
                if selected_node:
                    await self.sync_container_to_node(service_name, selected_node, cluster_key)
        
        elif rule.strategy == SyncStrategy.CUSTOM:
            for node in online_nodes:
                if node.get("id") in rule.target_nodes:
                    await self.sync_container_to_node(service_name, node, cluster_key)
    
    def get_container_distribution(self) -> Dict[str, List[str]]:
        """Get distribution of containers across nodes"""
        distribution: Dict[str, List[str]] = {}
        
        for state_key, state in self.container_states.items():
            node_id = state.node_id
            if node_id not in distribution:
                distribution[node_id] = []
            distribution[node_id].append(state.service_name)
        
        return distribution
    
    async def migrate_container(self, service_name: str, source_node_id: str,
                               target_node: Dict, cluster_key: str) -> bool:
        """
        Migrate a container from one node to another
        
        Args:
            service_name: Service to migrate
            source_node_id: Source node identifier
            target_node: Target node information
            cluster_key: Cluster authentication key
        
        Returns:
            True if migration successful, False otherwise
        """
        success = await self.sync_container_to_node(service_name, target_node, cluster_key)
        
        if success:
            source_key = f"{service_name}_{source_node_id}"
            if source_key in self.container_states:
                del self.container_states[source_key]
                self.save_sync_state()
            
            return True
        
        return False
    
    def get_sync_status(self) -> Dict:
        """Get overall synchronization status"""
        total_containers = len(self.container_states)
        running_containers = sum(
            1 for state in self.container_states.values()
            if state.status == "running"
        )
        
        return {
            "total_synced_containers": total_containers,
            "running_containers": running_containers,
            "sync_rules_count": len(self.sync_rules),
            "last_sync": datetime.now().isoformat()
        }

_sync_manager_instance = None

def get_sync_manager() -> ContainerSyncManager:
    """Get or create global sync manager instance"""
    global _sync_manager_instance
    if _sync_manager_instance is None:
        _sync_manager_instance = ContainerSyncManager()
    return _sync_manager_instance
