"""
Container Synchronization Module for Upcode Harbor Cluster Management

Handles container state synchronization across cluster nodes.
"""

from typing import List, Dict, Optional
from datetime import datetime
import json
import os
from lib.secure_store import secure_write_json

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
        try:
            data = {
                name: rule.to_dict()
                for name, rule in self.sync_rules.items()
            }
            secure_write_json(SYNC_RULES_FILE, data)
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
        try:
            data = {
                key: state.to_dict()
                for key, state in self.container_states.items()
            }
            secure_write_json(SYNC_STATE_FILE, data)
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
        raise RuntimeError(
            "Container synchronization is disabled until volumes, secrets, "
            "networks, images, port conflicts, and rollback are handled transactionally"
        )
    
    async def sync_all_containers(self, nodes: List[Dict], cluster_key: str):
        """Reject synchronization until transactional replication is implemented."""
        raise RuntimeError("Container synchronization is disabled")
    
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
        """Reject migration until source stop and rollback are transactional."""
        raise RuntimeError("Container migration is disabled")
    
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
