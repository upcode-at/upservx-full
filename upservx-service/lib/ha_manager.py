"""
High Availability Manager for UpservX Cluster.

Handles:
- Heartbeat tracking from all nodes
- Master failure detection
- Automatic master election (Bully algorithm by priority/IP)
- Virtual IP (VIP) management via Linux `ip` command
- Failover coordination
"""

import json
import os
import subprocess
import threading
import time
import socket
from datetime import datetime
from typing import Optional

import httpx

HA_CONFIG_FILE = "/etc/upservx/ha.json"
HA_HEARTBEATS_FILE = "/etc/upservx/ha_heartbeats.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "vip": "",
    "vip_interface": "",
    "heartbeat_interval": 5,
    "failure_threshold": 3,
    "priority": 100,  # lower = higher priority to become master
    "last_election": None,
    "active_master": None,
    "active_master_ip": None,
}

_ha_manager_instance: Optional["HAManager"] = None
_ha_lock = threading.Lock()


def get_ha_manager() -> "HAManager":
    global _ha_manager_instance
    with _ha_lock:
        if _ha_manager_instance is None:
            _ha_manager_instance = HAManager()
        return _ha_manager_instance


class HAManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._running = False
        self.config = self._load_config()
        self.heartbeats: dict = self._load_heartbeats()
        self._vip_prefix = self._extract_vip_prefix()  # Cache VIP prefix length

        if self.config.get("enabled"):
            self.start()

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def _extract_vip_prefix(self) -> str:
        """Extract and cache the subnet prefix from VIP config."""
        vip = self.config.get("vip", "")
        if "/" in vip:
            return vip.split("/")[1]
        return "24"  # Default prefix if not specified

    def _load_config(self) -> dict:
        if os.path.exists(HA_CONFIG_FILE):
            try:
                with open(HA_CONFIG_FILE, "r") as f:
                    data = json.load(f)
                # Merge with defaults so new keys are available
                merged = {**DEFAULT_CONFIG, **data}
                return merged
            except Exception:
                pass
        return {**DEFAULT_CONFIG}

    def _save_config(self):
        os.makedirs(os.path.dirname(HA_CONFIG_FILE), exist_ok=True)
        with open(HA_CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def _load_heartbeats(self) -> dict:
        if os.path.exists(HA_HEARTBEATS_FILE):
            try:
                with open(HA_HEARTBEATS_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_heartbeats(self):
        os.makedirs(os.path.dirname(HA_HEARTBEATS_FILE), exist_ok=True)
        with open(HA_HEARTBEATS_FILE, "w") as f:
            json.dump(self.heartbeats, f, indent=2)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> dict:
        """Get current config (always reloads from disk to ensure freshness)."""
        with self._lock:
            current = self._load_config()
            return {**current}

    def update_config(self, **kwargs) -> dict:
        with self._lock:
            for key, value in kwargs.items():
                if key in DEFAULT_CONFIG or key == "enabled":
                    self.config[key] = value
            self._save_config()
            config_snapshot = {**self.config}
            
            # Update cached VIP prefix if VIP was changed
            if "vip" in kwargs:
                self._vip_prefix = self._extract_vip_prefix()

        # Push updated config to all peer nodes (fire-and-forget, in background)
        # Only push non-transient shared config – election results are pushed via master-update
        threading.Thread(
            target=self._push_config_to_peers,
            args=(config_snapshot,),
            daemon=True,
        ).start()

        return config_snapshot

    def _push_config_to_peers(self, config: dict) -> None:
        """Push HA config to all known cluster nodes."""
        try:
            from api.cluster import list_all_nodes, read_master_config, get_local_ip
            import socket as _socket

            master_cfg = read_master_config()
            if not master_cfg:
                return  # only master pushes config
            cluster_key = master_cfg.get("key")
            my_hostname = _socket.gethostname()

            # Strip transient per-node fields and election state (pushed separately via master-update)
            payload = {k: v for k, v in config.items()
                       if k not in ("active_master", "active_master_ip", "last_election")}

            for node in list_all_nodes():
                if node.get("hostname") == my_hostname:
                    continue
                ip = node.get("ip_address")
                port = node.get("port", 9500)
                try:
                    httpx.post(
                        f"http://{ip}:{port}/cluster/ha/config-sync",
                        json=payload,
                        headers={"Authorization": f"Bearer {cluster_key}"},
                        timeout=5.0,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def enable(self) -> dict:
        self.update_config(enabled=True)
        self.start()
        return self.config

    def disable(self) -> dict:
        self.stop()
        self.update_config(enabled=False)
        # Release VIP if we hold it
        if self.config.get("vip") and self.config.get("vip_interface"):
            self._release_vip_safe()
        return self.config

    def apply_synced_config(self, incoming: dict) -> None:
        """Apply a HA config received from the master node (no re-broadcast)."""
        with self._lock:
            for key, value in incoming.items():
                if key in DEFAULT_CONFIG:
                    self.config[key] = value
            self._save_config()

        # Restart heartbeat loop if enabled state changed
        if self.config.get("enabled") and not self._running:
            self.start()
        elif not self.config.get("enabled") and self._running:
            self.stop()

    def record_election_result(self, winner_hostname: str, winner_ip: str) -> None:
        """Record election result locally (no re-broadcast)."""
        now = datetime.now().isoformat()
        with self._lock:
            self.config["active_master"] = winner_hostname
            self.config["active_master_ip"] = winner_ip
            self.config["last_election"] = now
            self._save_config()

    def start(self):
        """Start the background heartbeat loop."""
        if self._running:
            return
        self._running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="ha-heartbeat"
        )
        self._heartbeat_thread.start()

    def stop(self):
        """Stop the background heartbeat loop."""
        self._running = False

    # ------------------------------------------------------------------
    # Heartbeat recording
    # ------------------------------------------------------------------

    def record_heartbeat(self, hostname: str, ip_address: str, port: int,
                         role: str, priority: int = 100) -> None:
        """Called when a heartbeat is received from a node."""
        with self._lock:
            self.heartbeats[hostname] = {
                "hostname": hostname,
                "ip_address": ip_address,
                "port": port,
                "role": role,
                "priority": priority,
                "last_seen": datetime.now().isoformat(),
                "alive": True,
            }
            self._save_heartbeats()

    def get_heartbeat_status(self) -> list:
        """Return heartbeat status for all known nodes with alive/stale flag."""
        with self._lock:
            interval = self.config.get("heartbeat_interval", 5)
            threshold = self.config.get("failure_threshold", 3)
            max_age = interval * threshold * 2  # seconds

            result = []
            now = datetime.now()
            for hostname, hb in self.heartbeats.items():
                try:
                    last = datetime.fromisoformat(hb["last_seen"])
                    age = (now - last).total_seconds()
                    alive = age < max_age
                except Exception:
                    alive = False
                    age = -1
                result.append({
                    **hb,
                    "alive": alive,
                    "age_seconds": round(age, 1),
                })
            return result

    # ------------------------------------------------------------------
    # VIP management
    # ------------------------------------------------------------------

    def assign_vip(self, vip: str, interface: str) -> bool:
        """Create a virtual interface and assign the VIP to it."""
        try:
            # Extract plain IP (without prefix)
            vip_ip = vip.split("/")[0] if "/" in vip else vip
            
            # Use stored prefix or extract from config
            if "/" in vip:
                vip_prefix = vip.split("/")[1]
                self._vip_prefix = vip_prefix  # Update cached prefix
            else:
                vip_prefix = self._vip_prefix
            
            vip_cidr = f"{vip_ip}/{vip_prefix}"
            vip_interface = f"{interface}:vip"  # Create virtual interface name

            # Check if already assigned on the virtual interface
            check = subprocess.run(
                ["ip", "addr", "show", "dev", vip_interface],
                capture_output=True, text=True, timeout=5
            )
            if check.returncode == 0 and vip_ip in check.stdout:
                return True  # already owner on virtual interface

            # Create the virtual interface with IP
            result = subprocess.run(
                ["ip", "addr", "add", vip_cidr, "dev", vip_interface],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0 and "RTNETLINK answers: File exists" not in result.stderr:
                return False

            # Bring up the virtual interface
            subprocess.run(
                ["ip", "link", "set", vip_interface, "up"],
                capture_output=True, text=True, timeout=5
            )

            # Send gratuitous ARP so network switches update their tables
            subprocess.run(
                ["arping", "-c", "3", "-A", "-I", vip_interface, vip_ip],
                capture_output=True, timeout=5
            )
            return True
        except Exception:
            return False

    def release_vip(self, vip: str, interface: str) -> bool:
        """Remove the virtual interface that holds the VIP."""
        try:
            vip_interface = f"{interface}:vip"  # Name of virtual interface

            # Simply delete the virtual interface (cleaner than manually removing the IP)
            result = subprocess.run(
                ["ip", "link", "del", vip_interface],
                capture_output=True, text=True, timeout=5
            )
            # Success if deleted or already gone
            return result.returncode == 0 or "does not exist" in result.stderr.lower() or "not found" in result.stderr.lower()
        except Exception:
            return False

    def _release_vip_safe(self):
        vip = self.config.get("vip", "")
        iface = self.config.get("vip_interface", "")
        if vip and iface:
            self.release_vip(vip, iface)

    def is_vip_owner(self) -> bool:
        """Check if this node currently holds the VIP (on its virtual interface)."""
        vip_ip = self.config.get("vip", "").split("/")[0]
        iface = self.config.get("vip_interface", "")
        if not vip_ip or not iface:
            return False
        try:
            vip_interface = f"{iface}:vip"  # Name of virtual interface
            result = subprocess.run(
                ["ip", "addr", "show", "dev", vip_interface],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0 and vip_ip in result.stdout
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Master election
    # ------------------------------------------------------------------

    def _get_local_hostname(self) -> str:
        return socket.gethostname()

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def trigger_election(self) -> dict:
        """
        Bully election: collect votes from reachable nodes,
        node with lowest priority (or IP as tiebreaker) wins.
        Returns info about who is the new master.
        Does NOT assign VIP – only records election result and notifies other nodes.
        """
        from api.cluster import (  # lazy import to avoid circular
            list_all_nodes, read_master_config, NODES_DIR
        )

        candidates = []
        my_hostname = self._get_local_hostname()
        my_ip = self._get_local_ip()
        my_priority = self.config.get("priority", 100)

        # Include self
        candidates.append({
            "hostname": my_hostname,
            "ip_address": my_ip,
            "priority": my_priority,
            "reachable": True,
        })

        # Probe all known nodes
        known_nodes = list_all_nodes()
        cluster_key = None
        master_cfg = read_master_config()
        if master_cfg:
            cluster_key = master_cfg.get("key")

        for node in known_nodes:
            if node.get("hostname") == my_hostname:
                continue
            node_ip = node.get("ip_address")
            node_port = node.get("port", 9500)
            reachable = False
            node_priority = 100

            if cluster_key:
                try:
                    resp = httpx.get(
                        f"http://{node_ip}:{node_port}/cluster/ha/vote",
                        headers={"Authorization": f"Bearer {cluster_key}"},
                        timeout=3.0,
                    )
                    if resp.status_code == 200:
                        vote_data = resp.json()
                        reachable = True
                        node_priority = vote_data.get("priority", 100)
                except Exception:
                    pass

            candidates.append({
                "hostname": node.get("hostname"),
                "ip_address": node_ip,
                "priority": node_priority,
                "reachable": reachable,
            })

        # Choose winner: lowest priority, then lowest IP as tiebreaker
        reachable_candidates = [c for c in candidates if c["reachable"]]
        if not reachable_candidates:
            reachable_candidates = candidates  # fallback

        winner = min(
            reachable_candidates,
            key=lambda c: (c["priority"], c["ip_address"])
        )

        i_win = winner["hostname"] == my_hostname

        # Record election result locally (no VIP assignment yet)
        self.record_election_result(winner["hostname"], winner["ip_address"])

        # Notify all nodes of the new master (includes active_master + last_election)
        for node in known_nodes:
            if node.get("hostname") == my_hostname:
                continue
            try:
                httpx.post(
                    f"http://{node.get('ip_address')}:{node.get('port', 9500)}/cluster/ha/master-update",
                    json={
                        "new_master": winner["hostname"],
                        "new_master_ip": winner["ip_address"],
                        "last_election": self.config.get("last_election"),
                    },
                    headers={"Authorization": f"Bearer {cluster_key}"},
                    timeout=3.0,
                )
            except Exception:
                pass

        return {
            "winner": winner,
            "candidates": candidates,
            "i_am_new_master": i_win,
        }

    def apply_election_result_with_vip(self) -> None:
        """
        After election is decided, apply VIP assignment based on result.
        Call this only when you want VIP to be assigned (e.g., after manual failover).
        """
        my_hostname = self._get_local_hostname()
        active_master = self.config.get("active_master")

        if active_master == my_hostname:
            # I am the new master – take VIP
            vip = self.config.get("vip", "")
            iface = self.config.get("vip_interface", "")
            if vip and iface:
                self.assign_vip(vip, iface)
        else:
            # I am not the new master – release VIP if I hold it
            vip = self.config.get("vip", "")
            iface = self.config.get("vip_interface", "")
            if vip and iface and self.is_vip_owner():
                self.release_vip(vip, iface)

    # ------------------------------------------------------------------
    # Failover
    # ------------------------------------------------------------------

    def perform_failover(self, reason: str = "manual") -> dict:
        """Trigger a failover. Runs election and applies VIP assignment."""
        result = self.trigger_election()
        # Only assign VIP when failover is explicitly triggered (manual)
        self.apply_election_result_with_vip()
        return {
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "new_master": result["winner"]["hostname"],
            "i_am_new_master": result["i_am_new_master"],
            "candidates": result["candidates"],
        }

    # ------------------------------------------------------------------
    # HA Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return comprehensive HA status."""
        from api.cluster import is_master_node, is_child_node  # lazy

        # Always reload config from disk to get latest values (including changes from heartbeat loop)
        current_config = self._load_config()

        hb_status = self.get_heartbeat_status()
        alive_count = sum(1 for h in hb_status if h["alive"])

        return {
            "enabled": current_config.get("enabled", False),
            "vip": current_config.get("vip", ""),
            "vip_interface": current_config.get("vip_interface", ""),
            "vip_owner": self.is_vip_owner(),
            "active_master": current_config.get("active_master"),
            "last_election": current_config.get("last_election"),
            "heartbeat_interval": current_config.get("heartbeat_interval", 5),
            "failure_threshold": current_config.get("failure_threshold", 3),
            "priority": current_config.get("priority", 100),
            "my_hostname": self._get_local_hostname(),
            "my_ip": self._get_local_ip(),
            "is_master": is_master_node(),
            "is_child": is_child_node(),
            "total_nodes_tracked": len(hb_status),
            "alive_nodes": alive_count,
            "heartbeats": hb_status,
        }

    # ------------------------------------------------------------------
    # Background heartbeat loop
    # ------------------------------------------------------------------

    def _heartbeat_loop(self):
        """Background thread: send heartbeats and check master health."""
        from api.cluster import (
            is_master_node, is_child_node, read_child_config,
            list_all_nodes, read_master_config
        )

        consecutive_master_failures = 0

        while self._running:
            try:
                interval = self.config.get("heartbeat_interval", 5)
                threshold = self.config.get("failure_threshold", 3)

                if is_child_node():
                    # Child: send heartbeat to master
                    child_cfg = read_child_config()
                    if child_cfg:
                        master_ip = child_cfg.get("master_ip")
                        master_port = child_cfg.get("master_port", 9500)
                        cluster_key = child_cfg.get("cluster_key") or child_cfg.get("key")

                        try:
                            resp = httpx.post(
                                f"http://{master_ip}:{master_port}/cluster/ha/heartbeat",
                                json={
                                    "hostname": self._get_local_hostname(),
                                    "ip_address": self._get_local_ip(),
                                    "port": 9500,
                                    "role": "child",
                                    "priority": self.config.get("priority", 100),
                                },
                                headers={"Authorization": f"Bearer {cluster_key}"},
                                timeout=3.0,
                            )
                            if resp.status_code == 200:
                                consecutive_master_failures = 0

                                # Also record own heartbeat locally
                                self.record_heartbeat(
                                    self._get_local_hostname(),
                                    self._get_local_ip(),
                                    9500, "child",
                                    self.config.get("priority", 100)
                                )
                            else:
                                consecutive_master_failures += 1
                        except Exception:
                            consecutive_master_failures += 1

                        # Master not responding → trigger election
                        if consecutive_master_failures >= threshold:
                            consecutive_master_failures = 0
                            self.perform_failover(reason="master_unreachable")

                elif is_master_node():
                    # Master: record own heartbeat
                    self.record_heartbeat(
                        self._get_local_hostname(),
                        self._get_local_ip(),
                        9500, "master",
                        self.config.get("priority", 100)
                    )
                    # VIP is only assigned during failover or explicit triggers, not here

            except Exception:
                pass

            time.sleep(self.config.get("heartbeat_interval", 5))
