"""
High Availability API endpoints for UpservX Cluster.

Endpoints:
  GET  /cluster/ha              - Get HA config + status
  PUT  /cluster/ha              - Update HA config (+ push to all nodes)
  POST /cluster/ha/enable       - Enable HA
  POST /cluster/ha/disable      - Disable HA
  GET  /cluster/ha/status       - Get live HA status (heartbeats, VIP, etc.)
  POST /cluster/ha/heartbeat    - Receive heartbeat from a node
  GET  /cluster/ha/vote         - Return this node's election vote info
  POST /cluster/ha/master-update - Notify this node of a new master
    POST /cluster/ha/vip-owner-update - Notify this node who currently owns the VIP
  POST /cluster/ha/failover     - Trigger manual failover / election
  POST /cluster/ha/config-sync  - Receive synced HA config from master
  GET  /cluster/ha/config       - Return this node's HA config (for initial sync on join)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from lib.cluster_security import CLUSTER_TLS_PORT
from lib.ha_manager import get_ha_manager
from lib.logger import log_system

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class HAConfigUpdate(BaseModel):
    vip: Optional[str] = None
    vip_interface: Optional[str] = None
    heartbeat_interval: Optional[int] = None
    failure_threshold: Optional[int] = None
    priority: Optional[int] = None


class HeartbeatPayload(BaseModel):
    hostname: str
    ip_address: str
    port: int = CLUSTER_TLS_PORT
    role: str = "child"
    priority: int = 100


class MasterUpdatePayload(BaseModel):
    new_master: str
    new_master_ip: str
    last_election: Optional[str] = None


class FailoverRequest(BaseModel):
    reason: str = "manual"


class VIPOwnerUpdatePayload(BaseModel):
    owner_hostname: Optional[str] = None
    owner_ip: Optional[str] = None
    timestamp: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/cluster/ha")
async def get_ha_config():
    """Return current HA configuration."""
    ha = get_ha_manager()
    return ha.get_config()


@router.put("/cluster/ha")
async def update_ha_config(payload: HAConfigUpdate):
    """Update HA configuration fields (does not enable/disable HA)."""
    ha = get_ha_manager()
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    config = ha.update_config(**updates)
    log_system(f"[HA] Config updated: {updates}")
    return config


@router.post("/cluster/ha/enable")
async def enable_ha():
    """Enable High Availability mode and start heartbeat loop."""
    ha = get_ha_manager()
    config = ha.enable()
    log_system("[HA] High Availability enabled")
    return {"message": "HA enabled", "config": config}


@router.post("/cluster/ha/disable")
async def disable_ha():
    """Disable High Availability mode and release VIP if held."""
    ha = get_ha_manager()
    config = ha.disable()
    log_system("[HA] High Availability disabled")
    return {"message": "HA disabled", "config": config}


@router.get("/cluster/ha/status")
async def get_ha_status():
    """Return live HA status including heartbeats, VIP ownership and node health."""
    ha = get_ha_manager()
    return ha.get_status()


@router.post("/cluster/ha/heartbeat")
async def receive_heartbeat(payload: HeartbeatPayload):
    """
    Called by child nodes to report they are alive.
    The master records the heartbeat timestamp.
    """
    ha = get_ha_manager()
    ha.record_heartbeat(
        hostname=payload.hostname,
        ip_address=payload.ip_address,
        port=payload.port,
        role=payload.role,
        priority=payload.priority,
    )
    return {"acknowledged": True, "timestamp": __import__("datetime").datetime.now().isoformat()}


@router.get("/cluster/ha/vote")
async def get_vote():
    """Return this node's election vote information (priority + hostname + IP)."""
    ha = get_ha_manager()
    status = ha.get_status()
    return {
        "hostname": status["my_hostname"],
        "ip_address": status["my_ip"],
        "priority": status["priority"],
    }


@router.post("/cluster/ha/master-update")
async def master_update(payload: MasterUpdatePayload):
    """
    Notify this node that a new master has been elected.
    Applies local election state and enforces VIP ownership on the dedicated HA interface.
    """
    ha = get_ha_manager()

    # Apply election result locally (winner assigns VIP on HA virtual interface,
    # previous owner releases it if needed).
    ha.handle_master_update(payload.new_master, payload.new_master_ip, payload.last_election)

    log_system(f"[HA] New master elected: {payload.new_master} ({payload.new_master_ip})")

    return {"status": "master_update_recorded"}


@router.post("/cluster/ha/vip-owner-update")
async def vip_owner_update(payload: VIPOwnerUpdatePayload):
    """Receive and persist cluster-wide VIP ownership state."""
    ha = get_ha_manager()
    ha.update_vip_owner(payload.owner_hostname, payload.owner_ip)
    return {
        "acknowledged": True,
        "owner_hostname": payload.owner_hostname,
        "owner_ip": payload.owner_ip,
    }


@router.post("/cluster/ha/failover")
async def trigger_failover(payload: FailoverRequest):
    """
    Manually trigger a failover / master election.
    The node with the lowest priority (configurable) wins.
    """
    ha = get_ha_manager()
    log_system(f"[HA] Manual failover triggered, reason: {payload.reason}")
    result = ha.perform_failover(reason=payload.reason)
    return result


@router.post("/cluster/ha/vip/assign")
async def assign_vip():
    """Manually assign the configured VIP to this node."""
    ha = get_ha_manager()
    vip = ha.config.get("vip", "")
    iface = ha.config.get("vip_interface", "")
    if not vip or not iface:
        raise HTTPException(status_code=400, detail="VIP and interface must be configured first")
    success = ha.assign_vip(vip, iface)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to assign VIP")
    log_system(f"[HA] VIP {vip} manually assigned to {iface}")
    return {"message": f"VIP {vip} assigned to interface {iface}"}


@router.post("/cluster/ha/vip/release")
async def release_vip():
    """Manually release the VIP from this node."""
    ha = get_ha_manager()
    vip = ha.config.get("vip", "")
    iface = ha.config.get("vip_interface", "")
    if not vip or not iface:
        raise HTTPException(status_code=400, detail="VIP and interface must be configured first")
    success = ha.release_vip(vip, iface)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to release VIP")
    log_system(f"[HA] VIP {vip} manually released from {iface}")
    return {"message": f"VIP {vip} released from interface {iface}"}


@router.post("/cluster/ha/config-sync")
async def receive_config_sync(payload: dict):
    """
    Called by the master node to push its HA config to this node.
    Applies the config locally without re-broadcasting.
    """
    ha = get_ha_manager()
    ha.apply_synced_config(payload)
    log_system(f"[HA] Config synced from master: {payload}")
    return {"acknowledged": True}


@router.get("/cluster/ha/config")
async def get_ha_config_for_sync():
    """
    Returns the shareable HA config for cluster sync.
    Node-local fields (vip, vip_interface, enabled, runtime state) are excluded
    because every node may have different interfaces and local settings.
    """
    ha = get_ha_manager()
    full = ha.get_config()
    local_only = {
        "enabled", "vip", "vip_interface",
        "active_master", "active_master_ip", "last_election",
        "vip_owner_hostname", "vip_owner_ip",
    }
    return {k: v for k, v in full.items() if k not in local_only}
