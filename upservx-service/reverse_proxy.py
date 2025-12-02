"""
Reverse Proxy and SSL Certificate Management using Nginx and Certbot.
"""

import os
import json
import subprocess
from typing import List, Optional, Dict
from pathlib import Path


NGINX_SITES_AVAILABLE = "/etc/nginx/sites-available"
NGINX_SITES_ENABLED = "/etc/nginx/sites-enabled"
NGINX_CONFIG_DIR = "/etc/nginx"
PROXY_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "proxy_config.json")
CERTBOT_DIR = "/etc/letsencrypt"


class ReverseProxyManager:
    """Manage Nginx reverse proxy configurations and SSL certificates."""
    
    def __init__(self):
        self.config_file = PROXY_CONFIG_FILE
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure necessary directories exist."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
    
    def _load_config(self) -> Dict:
        """Load proxy configuration from file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_config(self, config: Dict):
        """Save proxy configuration to file."""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def check_nginx_installed(self) -> bool:
        """Check if Nginx is installed."""
        try:
            result = subprocess.run(
                ["nginx", "-v"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def check_certbot_installed(self) -> bool:
        """Check if Certbot is installed."""
        try:
            result = subprocess.run(
                ["certbot", "--version"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    

    
    def get_nginx_status(self) -> Dict:
        """Get Nginx service status."""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "nginx"],
                capture_output=True,
                text=True
            )
            active = result.stdout.strip() == "active"
            
            result_enabled = subprocess.run(
                ["systemctl", "is-enabled", "nginx"],
                capture_output=True,
                text=True
            )
            enabled = result_enabled.stdout.strip() == "enabled"
            
            return {
                "installed": self.check_nginx_installed(),
                "active": active,
                "enabled": enabled
            }
        except Exception as e:
            return {
                "installed": False,
                "active": False,
                "enabled": False,
                "error": str(e)
            }
    
    def create_proxy_config(
        self,
        domain: str,
        backend_host: str = "127.0.0.1",
        backend_port: int = 8000,
        frontend_port: int = 3000,
        ssl_enabled: bool = False,
        force_ssl: bool = False
    ) -> Dict:
        """Create Nginx reverse proxy configuration."""
        config_name = domain.replace(".", "_")
        config_path = os.path.join(NGINX_SITES_AVAILABLE, config_name)
        enabled_path = os.path.join(NGINX_SITES_ENABLED, config_name)
        
        # Remove old config files if they exist (to avoid conflicts with old syntax)
        try:
            if os.path.exists(enabled_path):
                os.remove(enabled_path)
            if os.path.exists(config_path):
                os.remove(config_path)
        except Exception:
            pass
        
        # Build nginx config
        config_lines = []
        
        # Check if certificates exist
        cert_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
        key_path = f"/etc/letsencrypt/live/{domain}/privkey.pem"
        certs_exist = os.path.exists(cert_path) and os.path.exists(key_path)
        
        # HTTP server block (always needed for Let's Encrypt or redirect)
        config_lines.append(f"server {{")
        config_lines.append(f"    listen 80;")
        config_lines.append(f"    listen [::]:80;")
        config_lines.append(f"    server_name {domain};")
        config_lines.append(f"")
        
        if ssl_enabled and force_ssl and certs_exist:
            # Redirect all HTTP to HTTPS (only if certificates exist)
            config_lines.append(f"    return 301 https://$server_name$request_uri;")
        else:
            # Serve on HTTP (either no SSL, or SSL not forced, or certs don't exist yet)
            self._add_proxy_locations(config_lines, backend_host, backend_port, frontend_port)
        
        config_lines.append(f"}}")
        config_lines.append(f"")
        
        # HTTPS server block if SSL is enabled and certificates exist
        if ssl_enabled and certs_exist:
            config_lines.append(f"server {{")
            config_lines.append(f"    listen 443 ssl;")
            config_lines.append(f"    listen [::]:443 ssl;")
            config_lines.append(f"    http2 on;")
            config_lines.append(f"    server_name {domain};")
            config_lines.append(f"")
            config_lines.append(f"    ssl_certificate {cert_path};")
            config_lines.append(f"    ssl_certificate_key {key_path};")
            config_lines.append(f"    ssl_protocols TLSv1.2 TLSv1.3;")
            config_lines.append(f"    ssl_ciphers HIGH:!aNULL:!MD5;")
            config_lines.append(f"    ssl_prefer_server_ciphers on;")
            config_lines.append(f"")
            
            self._add_proxy_locations(config_lines, backend_host, backend_port, frontend_port)
            
            config_lines.append(f"}}")
        
        # Write config file
        try:
            with open(config_path, 'w') as f:
                f.write('\n'.join(config_lines))
            
            # Create symlink in sites-enabled
            if os.path.exists(enabled_path):
                os.remove(enabled_path)
            os.symlink(config_path, enabled_path)
            
            # Test nginx config
            test_result = subprocess.run(
                ["nginx", "-t"],
                capture_output=True,
                text=True
            )
            
            if test_result.returncode != 0:
                return {
                    "success": False,
                    "message": f"Nginx config test failed: {test_result.stderr}"
                }
            
            # Reload nginx
            subprocess.run(["systemctl", "reload", "nginx"], check=True)
            
            # Save to our config
            config = self._load_config()
            config[domain] = {
                "backend_host": backend_host,
                "backend_port": backend_port,
                "frontend_port": frontend_port,
                "ssl_enabled": ssl_enabled,
                "force_ssl": force_ssl,
                "config_file": config_path
            }
            self._save_config(config)
            
            return {
                "success": True,
                "message": "Proxy configuration created successfully",
                "config_path": config_path
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def _add_proxy_locations(self, config_lines: List[str], backend_host: str, backend_port: int, frontend_port: int):
        """Add proxy location blocks to config."""
        # API proxy location
        config_lines.append(f"    # API Backend")
        config_lines.append(f"    location /api/ {{")
        config_lines.append(f"        proxy_pass http://{backend_host}:{backend_port}/;")
        config_lines.append(f"        proxy_http_version 1.1;")
        config_lines.append(f"        proxy_set_header Upgrade $http_upgrade;")
        config_lines.append(f"        proxy_set_header Connection 'upgrade';")
        config_lines.append(f"        proxy_set_header Host $host;")
        config_lines.append(f"        proxy_set_header X-Real-IP $remote_addr;")
        config_lines.append(f"        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
        config_lines.append(f"        proxy_set_header X-Forwarded-Proto $scheme;")
        config_lines.append(f"        proxy_cache_bypass $http_upgrade;")
        config_lines.append(f"    }}")
        config_lines.append(f"")
        
        # WebSocket support for terminal
        config_lines.append(f"    # WebSocket Support")
        config_lines.append(f"    location /ws/ {{")
        config_lines.append(f"        proxy_pass http://{backend_host}:{backend_port}/ws/;")
        config_lines.append(f"        proxy_http_version 1.1;")
        config_lines.append(f"        proxy_set_header Upgrade $http_upgrade;")
        config_lines.append(f"        proxy_set_header Connection \"upgrade\";")
        config_lines.append(f"        proxy_set_header Host $host;")
        config_lines.append(f"        proxy_set_header X-Real-IP $remote_addr;")
        config_lines.append(f"        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
        config_lines.append(f"        proxy_set_header X-Forwarded-Proto $scheme;")
        config_lines.append(f"    }}")
        config_lines.append(f"")
        
        # Frontend proxy
        config_lines.append(f"    # Frontend")
        config_lines.append(f"    location / {{")
        config_lines.append(f"        proxy_pass http://{backend_host}:{frontend_port};")
        config_lines.append(f"        proxy_http_version 1.1;")
        config_lines.append(f"        proxy_set_header Upgrade $http_upgrade;")
        config_lines.append(f"        proxy_set_header Connection 'upgrade';")
        config_lines.append(f"        proxy_set_header Host $host;")
        config_lines.append(f"        proxy_cache_bypass $http_upgrade;")
        config_lines.append(f"    }}")
        config_lines.append(f"")
    
    def delete_proxy_config(self, domain: str) -> Dict:
        """Delete proxy configuration for a domain."""
        config_name = domain.replace(".", "_")
        config_path = os.path.join(NGINX_SITES_AVAILABLE, config_name)
        enabled_path = os.path.join(NGINX_SITES_ENABLED, config_name)
        
        try:
            # Remove symlink
            if os.path.exists(enabled_path):
                os.remove(enabled_path)
            
            # Remove config file
            if os.path.exists(config_path):
                os.remove(config_path)
            
            # Remove from our config
            config = self._load_config()
            if domain in config:
                del config[domain]
                self._save_config(config)
            
            # Reload nginx
            subprocess.run(["systemctl", "reload", "nginx"], check=True)
            
            return {"success": True, "message": "Proxy configuration deleted"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def list_proxy_configs(self) -> List[Dict]:
        """List all managed proxy configurations."""
        config = self._load_config()
        result = []
        
        for domain, settings in config.items():
            result.append({
                "domain": domain,
                **settings
            })
        
        return result
    
    def obtain_certificate(self, domain: str, email: str, webroot: bool = False) -> Dict:
        """Obtain Let's Encrypt SSL certificate for domain."""
        if not self.check_certbot_installed():
            return {"success": False, "message": "Certbot not installed"}
        
        try:
            # Use standalone method (temporarily stops nginx on port 80)
            # This works without nginx plugin being installed
            cmd = [
                "certbot", "certonly",
                "--standalone",
                "--preferred-challenges", "http",
                "-d", domain,
                "--email", email,
                "--agree-tos",
                "--non-interactive",
                "--pre-hook", "systemctl stop nginx",
                "--post-hook", "systemctl start nginx"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Update config to enable SSL
                config = self._load_config()
                if domain in config:
                    config[domain]["ssl_enabled"] = True
                    self._save_config(config)
                    
                    # Recreate nginx config with SSL
                    self.create_proxy_config(
                        domain=domain,
                        backend_host=config[domain]["backend_host"],
                        backend_port=config[domain]["backend_port"],
                        frontend_port=config[domain]["frontend_port"],
                        ssl_enabled=True,
                        force_ssl=config[domain].get("force_ssl", True)
                    )
                
                return {
                    "success": True,
                    "message": "Certificate obtained successfully",
                    "output": result.stdout
                }
            else:
                return {
                    "success": False,
                    "message": f"Certificate request failed: {result.stderr}"
                }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def renew_certificates(self) -> Dict:
        """Renew all Let's Encrypt certificates."""
        if not self.check_certbot_installed():
            return {"success": False, "message": "Certbot not installed"}
        
        try:
            cmd = ["certbot", "renew", "--quiet"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Reload nginx to use new certificates
                subprocess.run(["systemctl", "reload", "nginx"], capture_output=True)
                return {
                    "success": True,
                    "message": "Certificates renewed successfully"
                }
            else:
                return {
                    "success": False,
                    "message": f"Renewal failed: {result.stderr}"
                }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def list_certificates(self) -> List[Dict]:
        """List all installed SSL certificates."""
        if not self.check_certbot_installed():
            return []
        
        try:
            cmd = ["certbot", "certificates"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Parse output
                certificates = []
                lines = result.stdout.split('\n')
                current_cert = {}
                
                for line in lines:
                    line = line.strip()
                    if line.startswith("Certificate Name:"):
                        if current_cert:
                            certificates.append(current_cert)
                        current_cert = {"name": line.split(":", 1)[1].strip()}
                    elif line.startswith("Domains:"):
                        current_cert["domains"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Expiry Date:"):
                        current_cert["expiry"] = line.split(":", 1)[1].strip()
                    elif line.startswith("Certificate Path:"):
                        current_cert["cert_path"] = line.split(":", 1)[1].strip()
                
                if current_cert:
                    certificates.append(current_cert)
                
                return certificates
            else:
                return []
        except Exception:
            return []
    
    def revoke_certificate(self, domain: str) -> Dict:
        """Revoke and delete a certificate."""
        if not self.check_certbot_installed():
            return {"success": False, "message": "Certbot not installed"}
        
        try:
            cmd = ["certbot", "revoke", "--cert-name", domain, "--delete-after-revoke"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Update our config
                config = self._load_config()
                if domain in config:
                    config[domain]["ssl_enabled"] = False
                    self._save_config(config)
                    
                    # Recreate nginx config without SSL
                    self.create_proxy_config(
                        domain=domain,
                        backend_host=config[domain]["backend_host"],
                        backend_port=config[domain]["backend_port"],
                        frontend_port=config[domain]["frontend_port"],
                        ssl_enabled=False,
                        force_ssl=False
                    )
                
                return {
                    "success": True,
                    "message": "Certificate revoked successfully"
                }
            else:
                return {
                    "success": False,
                    "message": f"Revocation failed: {result.stderr}"
                }
        except Exception as e:
            return {"success": False, "message": str(e)}


# Global instance
reverse_proxy_manager = ReverseProxyManager()
