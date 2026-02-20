"""
Load Balancer Module for UpservX Cluster Management

Handles workload distribution across cluster nodes using various strategies.
"""

from typing import List, Dict, Optional
from enum import Enum
import json
import os

class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies"""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    RESOURCE_BASED = "resource_based"
    AFFINITY = "affinity"

class NodeCapacity:
    """Calculate and track node capacity"""
    
    def __init__(self, cpu_usage: float, memory_usage: float, disk_usage: float):
        self.cpu_usage = cpu_usage
        self.memory_usage = memory_usage
        self.disk_usage = disk_usage
    
    @property
    def total_load(self) -> float:
        """Calculate total load as weighted average"""
        return (self.cpu_usage * 0.4 + 
                self.memory_usage * 0.4 + 
                self.disk_usage * 0.2)
    
    @property
    def available_capacity(self) -> float:
        """Calculate available capacity (0-100)"""
        return 100 - self.total_load
    
    def can_handle_workload(self, required_cpu: float = 10, 
                           required_memory: float = 10) -> bool:
        """Check if node can handle additional workload"""
        return (100 - self.cpu_usage >= required_cpu and 
                100 - self.memory_usage >= required_memory)

class LoadBalancer:
    """Main load balancer class"""
    
    def __init__(self):
        self.round_robin_index = 0
        self.affinity_rules: Dict[str, str] = {}  # service_id -> node_id
    
    def select_node(self, 
                    nodes: List[Dict], 
                    strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_LOADED,
                    service_id: Optional[str] = None,
                    required_resources: Optional[Dict] = None) -> Optional[Dict]:
        """
        Select best node for workload placement
        
        Args:
            nodes: List of available cluster nodes
            strategy: Load balancing strategy to use
            service_id: Optional service identifier for affinity
            required_resources: Optional resource requirements
        
        Returns:
            Selected node or None if no suitable node found
        """
        if not nodes:
            return None
        
        online_nodes = [n for n in nodes if n.get("status") == "online"]
        if not online_nodes:
            return None
        
        if strategy == LoadBalancingStrategy.AFFINITY and service_id:
            return self._select_by_affinity(online_nodes, service_id)
        elif strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._select_round_robin(online_nodes)
        elif strategy == LoadBalancingStrategy.LEAST_LOADED:
            return self._select_least_loaded(online_nodes)
        elif strategy == LoadBalancingStrategy.RESOURCE_BASED:
            return self._select_by_resources(online_nodes, required_resources)
        
        return online_nodes[0]  # Fallback
    
    def _select_round_robin(self, nodes: List[Dict]) -> Dict:
        """Round-robin selection"""
        selected = nodes[self.round_robin_index % len(nodes)]
        self.round_robin_index += 1
        return selected
    
    def _select_least_loaded(self, nodes: List[Dict]) -> Dict:
        """Select node with least load"""
        def get_load(node):
            resources = node.get("resources", {})
            capacity = NodeCapacity(
                resources.get("cpu_usage", 0),
                resources.get("memory_usage", 0),
                resources.get("disk_usage", 0)
            )
            return capacity.total_load
        
        return min(nodes, key=get_load)
    
    def _select_by_resources(self, nodes: List[Dict], 
                            required_resources: Optional[Dict]) -> Optional[Dict]:
        """Select node based on resource requirements"""
        if not required_resources:
            return self._select_least_loaded(nodes)
        
        required_cpu = required_resources.get("cpu", 10)
        required_memory = required_resources.get("memory", 10)
        
        suitable_nodes = []
        for node in nodes:
            resources = node.get("resources", {})
            capacity = NodeCapacity(
                resources.get("cpu_usage", 0),
                resources.get("memory_usage", 0),
                resources.get("disk_usage", 0)
            )
            
            if capacity.can_handle_workload(required_cpu, required_memory):
                suitable_nodes.append((node, capacity.available_capacity))
        
        if not suitable_nodes:
            return None
        
        return max(suitable_nodes, key=lambda x: x[1])[0]
    
    def _select_by_affinity(self, nodes: List[Dict], service_id: str) -> Dict:
        """Select node based on affinity rules"""
        if service_id in self.affinity_rules:
            preferred_node_id = self.affinity_rules[service_id]
            for node in nodes:
                if node.get("id") == preferred_node_id:
                    return node
        
        return self._select_least_loaded(nodes)
    
    def set_affinity(self, service_id: str, node_id: str):
        """Set affinity rule for a service"""
        self.affinity_rules[service_id] = node_id
    
    def remove_affinity(self, service_id: str):
        """Remove affinity rule for a service"""
        if service_id in self.affinity_rules:
            del self.affinity_rules[service_id]
    
    def get_cluster_load_distribution(self, nodes: List[Dict]) -> Dict:
        """Get load distribution statistics across cluster"""
        if not nodes:
            return {
                "total_nodes": 0,
                "online_nodes": 0,
                "offline_nodes": 0,
                "average_cpu": 0,
                "average_memory": 0,
                "average_disk": 0,
                "total_capacity": 0
            }
        
        online_nodes = [n for n in nodes if n.get("status") == "online"]
        offline_nodes = [n for n in nodes if n.get("status") != "online"]
        
        if not online_nodes:
            return {
                "total_nodes": len(nodes),
                "online_nodes": 0,
                "offline_nodes": len(offline_nodes),
                "average_cpu": 0,
                "average_memory": 0,
                "average_disk": 0,
                "total_capacity": 0
            }
        
        total_cpu = sum(n.get("resources", {}).get("cpu_usage", 0) for n in online_nodes)
        total_memory = sum(n.get("resources", {}).get("memory_usage", 0) for n in online_nodes)
        total_disk = sum(n.get("resources", {}).get("disk_usage", 0) for n in online_nodes)
        
        avg_load = (total_cpu + total_memory + total_disk) / (3 * len(online_nodes))
        total_capacity = (100 - avg_load) * len(online_nodes)
        
        return {
            "total_nodes": len(nodes),
            "online_nodes": len(online_nodes),
            "offline_nodes": len(offline_nodes),
            "average_cpu": total_cpu / len(online_nodes),
            "average_memory": total_memory / len(online_nodes),
            "average_disk": total_disk / len(online_nodes),
            "total_capacity": total_capacity
        }
    
    def recommend_rebalancing(self, nodes: List[Dict], threshold: float = 30) -> List[Dict]:
        """
        Recommend nodes for workload rebalancing
        
        Args:
            nodes: List of cluster nodes
            threshold: Load difference threshold for rebalancing
        
        Returns:
            List of recommendations with source and target nodes
        """
        online_nodes = [n for n in nodes if n.get("status") == "online"]
        if len(online_nodes) < 2:
            return []
        
        node_loads = []
        for node in online_nodes:
            resources = node.get("resources", {})
            capacity = NodeCapacity(
                resources.get("cpu_usage", 0),
                resources.get("memory_usage", 0),
                resources.get("disk_usage", 0)
            )
            node_loads.append((node, capacity.total_load))
        
        node_loads.sort(key=lambda x: x[1])
        
        recommendations = []
        high_load_nodes = [n for n in node_loads if n[1] > 70]
        low_load_nodes = [n for n in node_loads if n[1] < 40]
        
        for high_node, high_load in high_load_nodes:
            for low_node, low_load in low_load_nodes:
                if high_load - low_load > threshold:
                    recommendations.append({
                        "source_node": high_node.get("id"),
                        "target_node": low_node.get("id"),
                        "load_difference": high_load - low_load,
                        "reason": f"High load on {high_node.get('hostname')} ({high_load:.1f}%), low load on {low_node.get('hostname')} ({low_load:.1f}%)"
                    })
        
        return recommendations

_load_balancer_instance = None

def get_load_balancer() -> LoadBalancer:
    """Get or create global load balancer instance"""
    global _load_balancer_instance
    if _load_balancer_instance is None:
        _load_balancer_instance = LoadBalancer()
    return _load_balancer_instance
