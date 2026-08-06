"""
Enhanced Metrics and Monitoring Module for Upcode Harbor Cluster Management

Provides advanced metrics collection, historical data tracking, and alerting.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import deque
import json
import os
import psutil
import socket
from lib.secure_store import ensure_config_directory, secure_write_json

UPCODE_HARBOR_CONFIG_DIR = "/etc/upcode-harbor"
METRICS_DIR = os.path.join(UPCODE_HARBOR_CONFIG_DIR, "metrics")
ALERTS_FILE = os.path.join(UPCODE_HARBOR_CONFIG_DIR, "alerts.json")

METRIC_RETENTION_HOURS = 24
METRIC_DATA_POINTS = 288  # 5-minute intervals for 24 hours

class MetricType:
    """Metric types"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    CONTAINER = "container"  # Container-specific metrics
    CUSTOM = "custom"

class AlertLevel:
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class MetricDataPoint:
    """Single metric data point"""
    
    def __init__(self, timestamp: str, value: float, metadata: Optional[Dict] = None):
        self.timestamp = timestamp
        self.value = value
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "value": self.value,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MetricDataPoint":
        return cls(
            timestamp=data["timestamp"],
            value=data["value"],
            metadata=data.get("metadata", {})
        )

class MetricSeries:
    """Time series data for a metric"""
    
    def __init__(self, metric_name: str, metric_type: str, node_id: str):
        self.metric_name = metric_name
        self.metric_type = metric_type
        self.node_id = node_id
        self.data_points: deque = deque(maxlen=METRIC_DATA_POINTS)
    
    def add_data_point(self, value: float, metadata: Optional[Dict] = None):
        """Add a new data point"""
        data_point = MetricDataPoint(
            timestamp=datetime.now().isoformat(),
            value=value,
            metadata=metadata
        )
        self.data_points.append(data_point)
    
    def get_latest(self) -> Optional[MetricDataPoint]:
        """Get latest data point"""
        return self.data_points[-1] if self.data_points else None
    
    def get_average(self, minutes: int = 5) -> float:
        """Get average value over last N minutes"""
        if not self.data_points:
            return 0.0
        
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent_points = [
            dp for dp in self.data_points
            if datetime.fromisoformat(dp.timestamp) > cutoff_time
        ]
        
        if not recent_points:
            return 0.0
        
        return sum(dp.value for dp in recent_points) / len(recent_points)
    
    def get_max(self, minutes: int = 5) -> float:
        """Get maximum value over last N minutes"""
        if not self.data_points:
            return 0.0
        
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent_points = [
            dp for dp in self.data_points
            if datetime.fromisoformat(dp.timestamp) > cutoff_time
        ]
        
        return max((dp.value for dp in recent_points), default=0.0)
    
    def to_dict(self) -> Dict:
        return {
            "metric_name": self.metric_name,
            "metric_type": self.metric_type,
            "node_id": self.node_id,
            "data_points": [dp.to_dict() for dp in self.data_points]
        }

class Alert:
    """Monitoring alert"""
    
    def __init__(self, alert_id: str, level: str, message: str, 
                 node_id: str, metric_name: str, value: float):
        self.alert_id = alert_id
        self.level = level
        self.message = message
        self.node_id = node_id
        self.metric_name = metric_name
        self.value = value
        self.timestamp = datetime.now().isoformat()
        self.acknowledged = False
    
    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "level": self.level,
            "message": self.message,
            "node_id": self.node_id,
            "metric_name": self.metric_name,
            "value": self.value,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Alert":
        alert = cls(
            alert_id=data["alert_id"],
            level=data["level"],
            message=data["message"],
            node_id=data["node_id"],
            metric_name=data["metric_name"],
            value=data["value"]
        )
        alert.timestamp = data["timestamp"]
        alert.acknowledged = data.get("acknowledged", False)
        return alert

class AlertRule:
    """Alert rule definition"""
    
    def __init__(self, rule_id: str, metric_name: str, condition: str,
                 threshold: float, level: str, message_template: str):
        self.rule_id = rule_id
        self.metric_name = metric_name
        self.condition = condition  # "greater_than", "less_than", "equals"
        self.threshold = threshold
        self.level = level
        self.message_template = message_template
        self.enabled = True
    
    def evaluate(self, value: float) -> bool:
        """Evaluate if alert should be triggered"""
        if not self.enabled:
            return False
        
        if self.condition == "greater_than":
            return value > self.threshold
        elif self.condition == "less_than":
            return value < self.threshold
        elif self.condition == "equals":
            return value == self.threshold
        
        return False
    
    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id,
            "metric_name": self.metric_name,
            "condition": self.condition,
            "threshold": self.threshold,
            "level": self.level,
            "message_template": self.message_template,
            "enabled": self.enabled
        }

class MetricsCollector:
    """Enhanced metrics collection and monitoring"""
    
    def __init__(self):
        self.metric_series: Dict[str, MetricSeries] = {}
        self.alerts: List[Alert] = []
        self.alert_rules: Dict[str, AlertRule] = {}
        self.ensure_metrics_dir()
        self.load_alerts()
        self.setup_default_alert_rules()
    
    def ensure_metrics_dir(self):
        """Ensure metrics directory exists"""
        ensure_config_directory(METRICS_DIR)
    
    def load_alerts(self):
        """Load alerts from file"""
        if os.path.exists(ALERTS_FILE):
            try:
                with open(ALERTS_FILE, 'r') as f:
                    data = json.load(f)
                    self.alerts = [Alert.from_dict(a) for a in data.get("alerts", [])]
            except Exception as e:
                print(f"Error loading alerts: {e}")
    
    def save_alerts(self):
        """Save alerts to file"""
        try:
            secure_write_json(
                ALERTS_FILE,
                {"alerts": [a.to_dict() for a in self.alerts]},
            )
        except Exception as e:
            print(f"Error saving alerts: {e}")
    
    def setup_default_alert_rules(self):
        """Setup default alert rules"""
        default_rules = [
            AlertRule(
                rule_id="high_cpu",
                metric_name="cpu_usage",
                condition="greater_than",
                threshold=80.0,
                level=AlertLevel.WARNING,
                message_template="High CPU usage on node {node_id}: {value:.1f}%"
            ),
            AlertRule(
                rule_id="critical_cpu",
                metric_name="cpu_usage",
                condition="greater_than",
                threshold=95.0,
                level=AlertLevel.CRITICAL,
                message_template="Critical CPU usage on node {node_id}: {value:.1f}%"
            ),
            AlertRule(
                rule_id="high_memory",
                metric_name="memory_usage",
                condition="greater_than",
                threshold=85.0,
                level=AlertLevel.WARNING,
                message_template="High memory usage on node {node_id}: {value:.1f}%"
            ),
            AlertRule(
                rule_id="critical_memory",
                metric_name="memory_usage",
                condition="greater_than",
                threshold=95.0,
                level=AlertLevel.CRITICAL,
                message_template="Critical memory usage on node {node_id}: {value:.1f}%"
            ),
            AlertRule(
                rule_id="high_disk",
                metric_name="disk_usage",
                condition="greater_than",
                threshold=90.0,
                level=AlertLevel.WARNING,
                message_template="High disk usage on node {node_id}: {value:.1f}%"
            )
        ]
        
        for rule in default_rules:
            self.alert_rules[rule.rule_id] = rule
    
    def collect_system_metrics(self, node_id: str) -> Dict:
        """Collect comprehensive system metrics"""
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        disk = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()
        
        net_io = psutil.net_io_counters()
        
        self._store_metric(node_id, "cpu_usage", MetricType.CPU, cpu_percent)
        self._store_metric(node_id, "memory_usage", MetricType.MEMORY, memory.percent)
        self._store_metric(node_id, "disk_usage", MetricType.DISK, disk.percent)
        
        self._check_alerts(node_id, "cpu_usage", cpu_percent)
        self._check_alerts(node_id, "memory_usage", memory.percent)
        self._check_alerts(node_id, "disk_usage", disk.percent)
        
        return {
            "cpu": {
                "usage": cpu_percent,
                "count": cpu_count,
                "frequency": cpu_freq.current if cpu_freq else None
            },
            "memory": {
                "usage": memory.percent,
                "total": memory.total,
                "available": memory.available,
                "used": memory.used
            },
            "swap": {
                "usage": swap.percent,
                "total": swap.total,
                "used": swap.used
            },
            "disk": {
                "usage": disk.percent,
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "read_bytes": disk_io.read_bytes if disk_io else 0,
                "write_bytes": disk_io.write_bytes if disk_io else 0
            },
            "network": {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv
            }
        }
    
    def _store_metric(self, node_id: str, metric_name: str, 
                     metric_type: str, value: float):
        """Store a metric data point"""
        key = f"{node_id}_{metric_name}"
        
        if key not in self.metric_series:
            self.metric_series[key] = MetricSeries(metric_name, metric_type, node_id)
        
        self.metric_series[key].add_data_point(value)
    
    def _check_alerts(self, node_id: str, metric_name: str, value: float):
        """Check alert rules for a metric"""
        for rule in self.alert_rules.values():
            if rule.metric_name == metric_name and rule.evaluate(value):
                alert_id = f"{node_id}_{metric_name}_{int(datetime.now().timestamp())}"
                message = rule.message_template.format(node_id=node_id, value=value)
                
                alert = Alert(
                    alert_id=alert_id,
                    level=rule.level,
                    message=message,
                    node_id=node_id,
                    metric_name=metric_name,
                    value=value
                )
                
                self.alerts.append(alert)
                self.save_alerts()
    
    def get_metric_history(self, node_id: str, metric_name: str,
                          minutes: int = 60) -> List[Dict]:
        """Get metric history for specified duration"""
        key = f"{node_id}_{metric_name}"
        
        if key not in self.metric_series:
            return []
        
        series = self.metric_series[key]
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        history = [
            dp.to_dict()
            for dp in series.data_points
            if datetime.fromisoformat(dp.timestamp) > cutoff_time
        ]
        
        return history
    
    def get_cluster_metrics_summary(self, nodes: List[Dict]) -> Dict:
        """Get comprehensive cluster metrics summary"""
        total_cpu = 0
        total_memory = 0
        total_disk = 0
        online_count = 0
        
        for node in nodes:
            if node.get("status") == "online":
                resources = node.get("resources", {})
                total_cpu += resources.get("cpu_usage", 0)
                total_memory += resources.get("memory_usage", 0)
                total_disk += resources.get("disk_usage", 0)
                online_count += 1
        
        avg_cpu = total_cpu / online_count if online_count > 0 else 0
        avg_memory = total_memory / online_count if online_count > 0 else 0
        avg_disk = total_disk / online_count if online_count > 0 else 0
        
        return {
            "cluster_average": {
                "cpu": avg_cpu,
                "memory": avg_memory,
                "disk": avg_disk
            },
            "cluster_total": {
                "cpu": total_cpu,
                "memory": total_memory,
                "disk": total_disk
            },
            "node_count": {
                "total": len(nodes),
                "online": online_count
            }
        }
    
    def get_active_alerts(self, level: Optional[str] = None) -> List[Dict]:
        """Get active (unacknowledged) alerts"""
        active_alerts = [
            a for a in self.alerts
            if not a.acknowledged
        ]
        
        if level:
            active_alerts = [a for a in active_alerts if a.level == level]
        
        return [a.to_dict() for a in active_alerts]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                self.save_alerts()
                return True
        return False
    
    def clear_old_alerts(self, hours: int = 24):
        """Clear alerts older than specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        self.alerts = [
            a for a in self.alerts
            if datetime.fromisoformat(a.timestamp) > cutoff_time
        ]
        self.save_alerts()

_metrics_collector_instance = None

def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector instance"""
    global _metrics_collector_instance
    if _metrics_collector_instance is None:
        _metrics_collector_instance = MetricsCollector()
    return _metrics_collector_instance
