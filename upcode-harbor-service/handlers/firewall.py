"""
Firewall Management using nftables

This module provides a Python interface to manage nftables firewall rules.
Supports managing tables, chains, and rules for input, output, and forward filtering.
"""

import subprocess
import json
import re
from typing import List, Dict, Optional, Any
from enum import Enum
from lib.logger import log_firewall

class ChainType(str, Enum):
    """Chain types in nftables"""
    FILTER = "filter"
    NAT = "nat"
    ROUTE = "route"

class ChainHook(str, Enum):
    """Chain hooks in nftables"""
    INPUT = "input"
    OUTPUT = "output"
    FORWARD = "forward"
    PREROUTING = "prerouting"
    POSTROUTING = "postrouting"

class ChainPolicy(str, Enum):
    """Chain policies"""
    ACCEPT = "accept"
    DROP = "drop"

class Protocol(str, Enum):
    """Supported protocols"""
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    ALL = "all"

class FirewallManager:
    """Manage nftables firewall rules"""
    
    def __init__(self):
        self.table_name = "upcode_harbor_filter"
        self.nat_table = "upcode_harbor_nat"
        self._ensure_tables()
    
    def _run_command(self, cmd: List[str]) -> tuple[str, str, int]:
        """Execute a command and return output, error, and return code"""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", 1
        except Exception as e:
            return "", str(e), 1
    
    def _ensure_tables(self):
        """Ensure base tables and chains exist"""
        self._run_command(["nft", "add", "table", "inet", self.table_name])
        
        chains = [
            ("input", "input", "filter", "0", "accept"),
            ("forward", "forward", "filter", "0", "accept"),
            ("output", "output", "filter", "0", "accept"),
        ]
        
        for chain_name, hook, chain_type, priority, policy in chains:
            self._run_command([
                "nft", "add", "chain", "inet", self.table_name, chain_name,
                f"{{ type {chain_type} hook {hook} priority {priority}; policy {policy}; }}"
            ])
        
        self._run_command(["nft", "add", "table", "ip", self.nat_table])
        
        nat_chains = [
            ("prerouting", "prerouting", "nat", "-100", "accept"),
            ("postrouting", "postrouting", "nat", "100", "accept"),
        ]
        
        for chain_name, hook, chain_type, priority, policy in nat_chains:
            self._run_command([
                "nft", "add", "chain", "ip", self.nat_table, chain_name,
                f"{{ type {chain_type} hook {hook} priority {priority}; policy {policy}; }}"
            ])
    
    def list_rules(self) -> Dict[str, Any]:
        """List all firewall rules in JSON format"""
        stdout, stderr, code = self._run_command(["nft", "-j", "list", "ruleset"])
        
        if code != 0:
            return {"error": stderr, "tables": []}
        
        try:
            ruleset = json.loads(stdout)
            return self._format_ruleset(ruleset)
        except json.JSONDecodeError:
            return {"error": "Failed to parse nftables output", "tables": []}
    
    def _format_ruleset(self, ruleset: Dict) -> Dict[str, Any]:
        """Format nftables ruleset for easier consumption"""
        formatted = {
            "tables": [],
            "rules": []
        }
        
        nftables_data = ruleset.get("nftables", [])
        
        for item in nftables_data:
            if "table" in item:
                table = item["table"]
                formatted["tables"].append({
                    "family": table.get("family"),
                    "name": table.get("name"),
                    "handle": table.get("handle")
                })
            
            elif "chain" in item:
                chain = item["chain"]
                formatted.setdefault("chains", []).append({
                    "family": chain.get("family"),
                    "table": chain.get("table"),
                    "name": chain.get("name"),
                    "type": chain.get("type"),
                    "hook": chain.get("hook"),
                    "policy": chain.get("policy"),
                    "handle": chain.get("handle")
                })
            
            elif "rule" in item:
                rule = item["rule"]
                formatted["rules"].append({
                    "family": rule.get("family"),
                    "table": rule.get("table"),
                    "chain": rule.get("chain"),
                    "expr": rule.get("expr"),
                    "handle": rule.get("handle"),
                    "comment": rule.get("comment"),
                    "formatted": self._format_rule_expression(rule.get("expr", []))
                })
        
        return formatted
    
    def _format_rule_expression(self, expressions: List[Dict]) -> str:
        """Convert nftables expression to human-readable format"""
        parts = []
        
        for expr in expressions:
            if "match" in expr:
                match = expr["match"]
                op = match.get("op", "==")
                left = match.get("left", {})
                right = match.get("right", {})
                
                if "protocol" in left:
                    protocol = left["protocol"]
                    parts.append(f"protocol {protocol}")
                
                if "payload" in left:
                    payload = left["payload"]
                    field = payload.get("field")
                    if field and isinstance(right, (int, str)):
                        parts.append(f"{field} {op} {right}")
            
            elif "accept" in expr:
                parts.append("accept")
            elif "drop" in expr:
                parts.append("drop")
            elif "reject" in expr:
                parts.append("reject")
            elif "counter" in expr:
                counter = expr["counter"]
                parts.append(f"counter packets {counter.get('packets', 0)} bytes {counter.get('bytes', 0)}")
        
        return " ".join(parts) if parts else "custom rule"
    
    def add_rule(
        self,
        chain: str,
        protocol: Optional[str] = None,
        port: Optional[int] = None,
        source_ip: Optional[str] = None,
        destination_ip: Optional[str] = None,
        action: str = "accept",
        comment: Optional[str] = None,
        position: Optional[int] = None
    ) -> Dict[str, Any]:
        """Add a new firewall rule"""
        
        rule_parts = []
        
        if source_ip:
            rule_parts.append(f"ip saddr {source_ip}")
        
        if destination_ip:
            rule_parts.append(f"ip daddr {destination_ip}")
        
        if protocol and protocol != "all":
            rule_parts.append(f"{protocol}")
            
            if port:
                rule_parts.append(f"dport {port}")
        
        rule_parts.append(action)
        
        if comment:
            rule_parts.append(f'comment "{comment}"')
        
        rule_expression = " ".join(rule_parts)
        
        cmd = ["nft"]
        
        if position is not None:
            cmd.extend(["insert", "rule", "inet", self.table_name, chain, "position", str(position)])
        else:
            cmd.extend(["add", "rule", "inet", self.table_name, chain])
        
        cmd.append(rule_expression)
        
        stdout, stderr, code = self._run_command(cmd)
        
        if code != 0:
            return {"success": False, "error": stderr}
        
        log_firewall(f"Added firewall rule: chain={chain}, protocol={protocol}, port={port}, action={action}")
        return {"success": True, "message": "Rule added successfully"}
    
    def delete_rule(self, chain: str, handle: int) -> Dict[str, Any]:
        """Delete a rule by handle"""
        cmd = ["nft", "delete", "rule", "inet", self.table_name, chain, "handle", str(handle)]
        stdout, stderr, code = self._run_command(cmd)
        
        if code != 0:
            return {"success": False, "error": stderr}
        
        log_firewall(f"Deleted firewall rule (chain={chain}, handle={handle})")
        return {"success": True, "message": "Rule deleted successfully"}
    
    def flush_chain(self, chain: str) -> Dict[str, Any]:
        """Flush all rules from a chain"""
        cmd = ["nft", "flush", "chain", "inet", self.table_name, chain]
        stdout, stderr, code = self._run_command(cmd)
        
        if code != 0:
            return {"success": False, "error": stderr}
        
        log_firewall(f"Flushed all rules from chain [{chain}]")
        return {"success": True, "message": f"Chain {chain} flushed successfully"}
    
    def set_chain_policy(self, chain: str, policy: str) -> Dict[str, Any]:
        """Set default policy for a chain"""
        if policy not in ["accept", "drop"]:
            return {"success": False, "error": "Policy must be 'accept' or 'drop'"}
        
        stdout, stderr, code = self._run_command([
            "nft", "-j", "list", "chain", "inet", self.table_name, chain
        ])
        
        if code != 0:
            return {"success": False, "error": f"Chain not found: {stderr}"}
        
        try:
            data = json.loads(stdout)
            chain_info = None
            
            for item in data.get("nftables", []):
                if "chain" in item:
                    chain_info = item["chain"]
                    break
            
            if not chain_info:
                return {"success": False, "error": "Chain info not found"}
            
            hook = chain_info.get("hook", "input")
            chain_type = chain_info.get("type", "filter")
            priority = chain_info.get("prio", 0)
            
            self._run_command(["nft", "delete", "chain", "inet", self.table_name, chain])
            
            cmd = [
                "nft", "add", "chain", "inet", self.table_name, chain,
                f"{{ type {chain_type} hook {hook} priority {priority}; policy {policy}; }}"
            ]
            
            stdout, stderr, code = self._run_command(cmd)
            
            if code != 0:
                return {"success": False, "error": stderr}
            
            log_firewall(f"Set chain [{chain}] policy to [{policy}]")
            return {"success": True, "message": f"Policy set to {policy} for chain {chain}"}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def add_port_forward(
        self,
        external_port: int,
        internal_ip: str,
        internal_port: int,
        protocol: str = "tcp",
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a port forwarding rule (DNAT)"""
        
        rule_parts = [f"{protocol} dport {external_port}"]
        rule_parts.append(f"dnat to {internal_ip}:{internal_port}")
        
        if comment:
            rule_parts.append(f'comment "{comment}"')
        
        rule_expression = " ".join(rule_parts)
        
        cmd = ["nft", "add", "rule", "ip", self.nat_table, "prerouting", rule_expression]
        stdout, stderr, code = self._run_command(cmd)
        
        if code != 0:
            return {"success": False, "error": stderr}
        
        log_firewall(f"Added port forward: external port {external_port} → {internal_ip}:{internal_port} ({protocol})")
        return {"success": True, "message": "Port forward added successfully"}
    
    def enable_masquerade(self, interface: str) -> Dict[str, Any]:
        """Enable masquerading (SNAT) for an interface"""
        cmd = [
            "nft", "add", "rule", "ip", self.nat_table, "postrouting",
            f"oifname {interface} masquerade"
        ]
        stdout, stderr, code = self._run_command(cmd)
        
        if code != 0:
            return {"success": False, "error": stderr}
        
        log_firewall(f"Enabled masquerading for interface [{interface}]")
        return {"success": True, "message": f"Masquerade enabled for {interface}"}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get firewall statistics"""
        stdout, stderr, code = self._run_command(["nft", "-j", "list", "ruleset"])
        
        if code != 0:
            return {"error": stderr}
        
        try:
            ruleset = json.loads(stdout)
            stats = {
                "total_rules": 0,
                "chains": {},
                "packets_processed": 0,
                "bytes_processed": 0
            }
            
            for item in ruleset.get("nftables", []):
                if "rule" in item:
                    stats["total_rules"] += 1
                    chain = item["rule"].get("chain")
                    
                    if chain:
                        stats["chains"][chain] = stats["chains"].get(chain, 0) + 1
                    
                    for expr in item["rule"].get("expr", []):
                        if "counter" in expr:
                            counter = expr["counter"]
                            stats["packets_processed"] += counter.get("packets", 0)
                            stats["bytes_processed"] += counter.get("bytes", 0)
            
            return stats
        
        except Exception as e:
            return {"error": str(e)}
    
    def save_rules(self, filepath: str = "/etc/upcode-harbor/nftables.conf") -> Dict[str, Any]:
        """Save current ruleset to file"""
        stdout, stderr, code = self._run_command(["nft", "list", "ruleset"])
        
        if code != 0:
            return {"success": False, "error": stderr}
        
        try:
            with open(filepath, "w") as f:
                f.write("#!/usr/sbin/nft -f\n\n")
                f.write(stdout)
            
            log_firewall(f"Saved firewall rules to [{filepath}]")
            return {"success": True, "message": f"Rules saved to {filepath}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def load_rules(self, filepath: str = "/etc/upcode-harbor/nftables.conf") -> Dict[str, Any]:
        """Load ruleset from file"""
        cmd = ["nft", "-f", filepath]
        stdout, stderr, code = self._run_command(cmd)
        
        if code != 0:
            return {"success": False, "error": stderr}
        
        log_firewall(f"Loaded firewall rules from [{filepath}]")
        return {"success": True, "message": f"Rules loaded from {filepath}"}

firewall_manager = FirewallManager()
