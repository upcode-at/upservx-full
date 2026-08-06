"""
High Availability Manager for Upcode Harbor Cluster.

Handles:
- Heartbeat tracking from all nodes
- Master failure detection
- Automatic master election (Bully algorithm by priority/IP)
- Virtual IP (VIP) management via Linux `ip` command
- Failover coordination
"""

import os
import subprocess
import threading
import time
import socket
from datetime import datetime
from typing import Optional

from lib.cluster_security import (
    CLUSTER_TLS_PORT,
    bootstrap_peer_ca_sync,
    cluster_url,
    normalize_cluster_port,
    signed_cluster_request_sync,
)
from lib.file_lock import InterProcessFileLock
from lib.secure_store import secure_read_json, secure_write_json

HA_CONFIG_ROOT = os.getenv("UPSERVX_CONFIG_DIR", "/etc/upservx")
HA_CONFIG_FILE = os.path.join(HA_CONFIG_ROOT, "ha.json")
HA_HEARTBEATS_FILE = os.path.join(HA_CONFIG_ROOT, "ha_heartbeats.json")
HA_LOCK_FILE = os.path.join(HA_CONFIG_ROOT, "ha.lock")

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
    "vip_owner_hostname": None,
    "vip_owner_ip": None,
}

_ha_manager_instance: Optional["HAManager"] = None
_ha_lock = threading.Lock()


def _signed_peer_request(
    method: str,
    peer: dict,
    path: str,
    cluster_key: str,
    *,
    json_data: dict | None = None,
    timeout: float = 5.0,
):
    """Send one HMAC-signed request over a peer-pinned TLS connection."""

    from api.cluster import write_child_config, write_node_config

    is_master_peer = bool(peer.get("master_ip"))
    host = peer.get("master_ip") if is_master_peer else peer.get("ip_address")
    if not host:
        raise ValueError("Cluster peer has no address")
    port = normalize_cluster_port(
        peer.get("master_port") if is_master_peer else peer.get("port")
    )
    ca_certificate = (
        peer.get("master_tls_ca") if is_master_peer else peer.get("tls_ca_certificate")
    )
    expected_node_id = (
        peer.get("hostname")
        or peer.get("assigned_hostname")
        or peer.get("master_hostname")
    )
    if not ca_certificate:
        ca_certificate, authenticated_node_id, port = bootstrap_peer_ca_sync(
            host,
            port,
            cluster_key,
            expected_node_id=expected_node_id,
        )
        if peer.get("master_ip"):
            peer["master_tls_ca"] = ca_certificate
            peer["master_hostname"] = authenticated_node_id
            peer["master_port"] = port
            write_child_config(peer)
        else:
            peer["tls_ca_certificate"] = ca_certificate
            peer["port"] = port
            write_node_config(str(peer.get("hostname") or authenticated_node_id), peer)

    return signed_cluster_request_sync(
        method,
        cluster_url(host, port, path),
        key=cluster_key,
        ca_certificate=ca_certificate,
        json_data=json_data,
        timeout=timeout,
    )


def get_ha_manager() -> "HAManager":
    global _ha_manager_instance
    with _ha_lock:
        if _ha_manager_instance is None:
            _ha_manager_instance = HAManager()
        return _ha_manager_instance


class HAManager:
    def __init__(self):
        self._lock = InterProcessFileLock(HA_LOCK_FILE)
        self._passive = os.getenv("UPSERVX_PASSIVE_PROCESS") == "1"
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._running = False
        self.config = self._load_config()
        self.heartbeats: dict = self._load_heartbeats()
        self._vip_prefix = self._extract_vip_prefix()  # Cache VIP prefix length

        if self.config.get("enabled") and not self._passive:
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

    def _parse_vip(self, vip: str) -> tuple[str, str]:
        """Return plain VIP IP and prefix length."""
        vip_ip = vip.split("/")[0] if "/" in vip else vip
        if "/" in vip:
            prefix = vip.split("/")[1]
            self._vip_prefix = prefix
        else:
            prefix = self._vip_prefix
        return vip_ip, prefix

    def _ha_virtual_interface(self, base_interface: str) -> str:
        """Return the real interface name — VIP is assigned directly on it (VRRP-style)."""
        return base_interface

    def _broadcast_vip_owner(self, owner_hostname: Optional[str], owner_ip: Optional[str]) -> None:
        """Broadcast current VIP owner to all known nodes."""
        try:
            from api.cluster import list_all_nodes, read_master_config, read_child_config

            master_cfg = read_master_config()
            child_cfg = read_child_config()
            cluster_key = None
            if master_cfg:
                cluster_key = master_cfg.get("key")
            elif child_cfg:
                cluster_key = child_cfg.get("cluster_key") or child_cfg.get("key")

            if not cluster_key:
                return

            my_hostname = self._get_local_hostname()
            payload = {
                "owner_hostname": owner_hostname,
                "owner_ip": owner_ip,
                "timestamp": datetime.now().isoformat(),
            }

            for node in list_all_nodes():
                if node.get("hostname") == my_hostname:
                    continue
                try:
                    _signed_peer_request(
                        "POST",
                        node,
                        "/cluster/ha/vip-owner-update",
                        cluster_key,
                        json_data=payload,
                        timeout=3.0,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def _set_vip_owner(self, owner_hostname: Optional[str], owner_ip: Optional[str], broadcast: bool = False) -> None:
        """Persist VIP owner and optionally broadcast to peers."""
        with self._lock:
            self.config = self._load_config()
            self.config["vip_owner_hostname"] = owner_hostname
            self.config["vip_owner_ip"] = owner_ip
            self._save_config()

        if broadcast:
            self._broadcast_vip_owner(owner_hostname, owner_ip)

    def _load_config(self) -> dict:
        data = secure_read_json(HA_CONFIG_FILE, missing=None)
        if data is None:
            return {**DEFAULT_CONFIG}
        if not isinstance(data, dict):
            raise RuntimeError("HA configuration must be a JSON object")
        return {**DEFAULT_CONFIG, **data}

    def _save_config(self):
        secure_write_json(HA_CONFIG_FILE, self.config)

    def _load_heartbeats(self) -> dict:
        data = secure_read_json(HA_HEARTBEATS_FILE, missing=None)
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise RuntimeError("HA heartbeat state must be a JSON object")
        return data

    def _save_heartbeats(self):
        secure_write_json(HA_HEARTBEATS_FILE, self.heartbeats)

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
            self.config = self._load_config()
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
            # and keep enabled local per node to avoid unintended remote disable/enable flips.
            payload = {k: v for k, v in config.items()
                       if k not in (
                           "enabled",
                           "active_master",
                           "active_master_ip",
                           "last_election",
                           "vip_owner_hostname",
                           "vip_owner_ip",
                       )}

            for node in list_all_nodes():
                if node.get("hostname") == my_hostname:
                    continue
                try:
                    _signed_peer_request(
                        "POST",
                        node,
                        "/cluster/ha/config-sync",
                        cluster_key,
                        json_data=payload,
                        timeout=5.0,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def enable(self) -> dict:
        self.update_config(enabled=True)
        if not self._passive:
            self.start()
        return self.config

    def disable(self) -> dict:
        self.stop()
        self.update_config(enabled=False)
        # Release VIP if we hold it
        if self.config.get("vip") and self.config.get("vip_interface"):
            self._release_vip_safe()
        return self.config

    # Keys that are node-local and must never be overwritten by config sync.
    # Interfaces, VIP address, and runtime state all differ per node.
    _LOCAL_ONLY_KEYS = {
        "enabled",
        "vip",
        "vip_interface",
        "active_master",
        "active_master_ip",
        "last_election",
        "vip_owner_hostname",
        "vip_owner_ip",
    }

    def apply_synced_config(self, incoming: dict) -> None:
        """Apply a HA config received from the master node (no re-broadcast)."""
        with self._lock:
            self.config = self._load_config()
            for key, value in incoming.items():
                if key in DEFAULT_CONFIG and key not in self._LOCAL_ONLY_KEYS:
                    self.config[key] = value
            self._save_config()

        # Restart heartbeat loop if enabled state changed
        if self.config.get("enabled") and not self._running and not self._passive:
            self.start()
        elif not self.config.get("enabled") and self._running:
            self.stop()

    def record_election_result(self, winner_hostname: str, winner_ip: str) -> None:
        """Record election result locally (no re-broadcast)."""
        now = datetime.now().isoformat()
        with self._lock:
            self.config = self._load_config()
            self.config["active_master"] = winner_hostname
            self.config["active_master_ip"] = winner_ip
            self.config["last_election"] = now
            self._save_config()

    def handle_master_update(self, winner_hostname: str, winner_ip: str, last_election: Optional[str] = None) -> None:
        """Apply election update locally and enforce VIP ownership state."""
        with self._lock:
            self.config = self._load_config()
            self.config["active_master"] = winner_hostname
            self.config["active_master_ip"] = winner_ip
            self.config["last_election"] = last_election or datetime.now().isoformat()
            self._save_config()

        vip = self.config.get("vip", "")
        iface = self.config.get("vip_interface", "")
        if not vip or not iface:
            return

        if winner_hostname == self._get_local_hostname():
            self.assign_vip(vip, iface)
        else:
            # Always attempt cleanup on non-winner nodes so stale VIP assignments
            # do not survive a manual failover because of a false negative owner check.
            self.release_vip(vip, iface, broadcast=False)

    def start(self):
        """Start the background heartbeat loop."""
        if self._passive:
            return
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
            self.heartbeats = self._load_heartbeats()
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
            self.config = self._load_config()
            self.heartbeats = self._load_heartbeats()
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
        """Assign VIP directly on the real interface (VRRP-style)."""
        try:
            vip_ip, vip_prefix = self._parse_vip(vip)
            vip_cidr = f"{vip_ip}/{vip_prefix}"

            check = subprocess.run(
                ["ip", "addr", "show", "dev", interface],
                capture_output=True, text=True, timeout=5
            )
            if check.returncode == 0 and vip_ip in check.stdout:
                self._set_vip_owner(self._get_local_hostname(), self._get_local_ip(), broadcast=True)
                return True

            result = subprocess.run(
                ["ip", "addr", "add", vip_cidr, "dev", interface],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0 and "RTNETLINK answers: File exists" not in result.stderr:
                return False

            # Send gratuitous ARP so network switches update their MAC tables
            subprocess.run(
                ["arping", "-c", "3", "-A", "-I", interface, vip_ip],
                capture_output=True, timeout=5
            )
            self._set_vip_owner(self._get_local_hostname(), self._get_local_ip(), broadcast=True)
            return True
        except Exception:
            return False

    def _delete_vip_from_interface(self, vip_cidr: str, device: str) -> bool:
        """Try to remove the VIP from a specific interface and treat missing state as success."""
        try:
            result = subprocess.run(
                ["ip", "addr", "del", vip_cidr, "dev", device],
                capture_output=True, text=True, timeout=5
            )
            stderr = (result.stderr or "").lower()
            return (
                result.returncode == 0
                or "cannot assign requested address" in stderr
                or "cannot find device" in stderr
                or "not found" in stderr
                or "no such process" in stderr
            )
        except Exception:
            return False

    def release_vip(self, vip: str, interface: str, broadcast: bool = True) -> bool:
        """Release VIP from the real interface and clean up any legacy placements."""
        try:
            vip_ip, vip_prefix = self._parse_vip(vip)
            vip_cidr = f"{vip_ip}/{vip_prefix}"

            base_removed = self._delete_vip_from_interface(vip_cidr, interface)
            alias_removed = self._delete_vip_from_interface(vip_cidr, f"{interface}:vip")
            # Clean up any old dummy interface that may exist from a previous version
            ha_iface = f"ha{''.join(ch for ch in interface if ch.isalnum())}"[:15]
            subprocess.run(
                ["ip", "link", "del", ha_iface],
                capture_output=True, text=True, timeout=5
            )

            success = base_removed or alias_removed
            if success and broadcast:
                self._set_vip_owner(None, None, broadcast=True)
            return success
        except Exception:
            return False

    def _release_vip_safe(self):
        vip = self.config.get("vip", "")
        iface = self.config.get("vip_interface", "")
        if vip and iface:
            self.release_vip(vip, iface)

    def is_vip_owner(self) -> bool:
        """Check if this node currently holds the VIP on the real interface."""
        vip_ip = self.config.get("vip", "").split("/")[0]
        iface = self.config.get("vip_interface", "")
        if not vip_ip or not iface:
            return False
        try:
            result = subprocess.run(
                ["ip", "addr", "show", "dev", iface],
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
        Winner/loser VIP state is enforced via master update handling.
        """
        from api.cluster import (  # lazy import to avoid circular
            get_cluster_key, list_all_nodes, read_master_config, NODES_DIR
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
        else:
            cluster_key = get_cluster_key()

        for node in known_nodes:
            if node.get("hostname") == my_hostname:
                continue
            node_ip = node.get("ip_address")
            reachable = False
            node_priority = 100

            if cluster_key:
                try:
                    resp = _signed_peer_request(
                        "GET",
                        node,
                        "/cluster/ha/vote",
                        cluster_key,
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

        # Apply election result locally so winner/loser state is enforced immediately.
        election_time = datetime.now().isoformat()
        self.handle_master_update(winner["hostname"], winner["ip_address"], election_time)

        # Notify all nodes of the new master (includes active_master + last_election)
        for node in known_nodes:
            if node.get("hostname") == my_hostname:
                continue
            try:
                _signed_peer_request(
                    "POST",
                    node,
                    "/cluster/ha/master-update",
                    cluster_key,
                    json_data={
                        "new_master": winner["hostname"],
                        "new_master_ip": winner["ip_address"],
                        "last_election": election_time,
                    },
                    timeout=3.0,
                )
            except Exception:
                pass

        return {
            "winner": winner,
            "candidates": candidates,
            "i_am_new_master": i_win,
        }

    # ------------------------------------------------------------------
    # Failover
    # ------------------------------------------------------------------

    def perform_failover(self, reason: str = "manual") -> dict:
        """Trigger a failover. Runs election and applies VIP ownership update."""
        result = self.trigger_election()
        return {
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "new_master": result["winner"]["hostname"],
            "i_am_new_master": result["i_am_new_master"],
            "candidates": result["candidates"],
        }

    def update_vip_owner(self, owner_hostname: Optional[str], owner_ip: Optional[str]) -> None:
        """Update VIP owner from inter-node broadcast."""
        self._set_vip_owner(owner_hostname, owner_ip, broadcast=False)

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
            "vip_ha_interface": self._ha_virtual_interface(current_config.get("vip_interface", "")),
            "vip_owner": self.is_vip_owner(),
            "vip_owner_hostname": current_config.get("vip_owner_hostname"),
            "vip_owner_ip": current_config.get("vip_owner_ip"),
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
                        cluster_key = child_cfg.get("cluster_key") or child_cfg.get("key")

                        try:
                            resp = _signed_peer_request(
                                "POST",
                                child_cfg,
                                "/cluster/ha/heartbeat",
                                cluster_key,
                                json_data={
                                    "hostname": self._get_local_hostname(),
                                    "ip_address": self._get_local_ip(),
                                    "port": CLUSTER_TLS_PORT,
                                    "role": "child",
                                    "priority": self.config.get("priority", 100),
                                },
                                timeout=3.0,
                            )
                            if resp.status_code == 200:
                                consecutive_master_failures = 0

                                # Also record own heartbeat locally
                                self.record_heartbeat(
                                    self._get_local_hostname(),
                                    self._get_local_ip(),
                                    CLUSTER_TLS_PORT, "child",
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
                        CLUSTER_TLS_PORT, "master",
                        self.config.get("priority", 100)
                    )
                    # VIP is only assigned during failover or explicit triggers, not here

            except Exception:
                pass

            time.sleep(self.config.get("heartbeat_interval", 5))
