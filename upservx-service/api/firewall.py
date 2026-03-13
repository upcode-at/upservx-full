"""
Firewall API endpoints for nftables management
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from lib.models import (
    FirewallRuleCreate,
    FirewallRuleDelete,
    FirewallChainPolicy,
    PortForwardCreate,
    MasqueradeCreate
)
from handlers.firewall import firewall_manager

router = APIRouter(prefix="/firewall", tags=["firewall"])


@router.get("/rules")
async def get_firewall_rules() -> Dict[str, Any]:
    """Get all firewall rules"""
    try:
        return firewall_manager.list_rules()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rules")
async def add_firewall_rule(rule: FirewallRuleCreate) -> Dict[str, Any]:
    """Add a new firewall rule"""
    try:
        result = firewall_manager.add_rule(
            chain=rule.chain,
            protocol=rule.protocol,
            port=rule.port,
            source_ip=rule.source_ip,
            destination_ip=rule.destination_ip,
            action=rule.action,
            comment=rule.comment,
            position=rule.position
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rules")
async def delete_firewall_rule(rule: FirewallRuleDelete) -> Dict[str, Any]:
    """Delete a firewall rule by handle"""
    try:
        result = firewall_manager.delete_rule(rule.chain, rule.handle)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chains/{chain}/flush")
async def flush_chain(chain: str) -> Dict[str, Any]:
    """Flush all rules from a chain"""
    try:
        result = firewall_manager.flush_chain(chain)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/chains/policy")
async def set_chain_policy(policy: FirewallChainPolicy) -> Dict[str, Any]:
    """Set default policy for a chain"""
    try:
        result = firewall_manager.set_chain_policy(policy.chain, policy.policy)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/port-forward")
async def add_port_forward(forward: PortForwardCreate) -> Dict[str, Any]:
    """Add a port forwarding rule"""
    try:
        result = firewall_manager.add_port_forward(
            external_port=forward.external_port,
            internal_ip=forward.internal_ip,
            internal_port=forward.internal_port,
            protocol=forward.protocol,
            comment=forward.comment
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/masquerade")
async def enable_masquerade(masquerade: MasqueradeCreate) -> Dict[str, Any]:
    """Enable masquerading for an interface"""
    try:
        result = firewall_manager.enable_masquerade(masquerade.interface)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_firewall_statistics() -> Dict[str, Any]:
    """Get firewall statistics"""
    try:
        return firewall_manager.get_statistics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save")
async def save_firewall_rules(filepath: str = "/etc/nftables.conf") -> Dict[str, Any]:
    """Save current firewall rules to file"""
    try:
        result = firewall_manager.save_rules(filepath)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load")
async def load_firewall_rules(filepath: str = "/etc/nftables.conf") -> Dict[str, Any]:
    """Load firewall rules from file"""
    try:
        result = firewall_manager.load_rules(filepath)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
