"""
Reverse Proxy and SSL Certificate Management using Nginx and Certbot.
"""

import os
import json
import re
import stat
import subprocess
import tempfile
from typing import List, Optional, Dict
from pathlib import Path
from lib.logger import log_proxy
from lib.privileged import require_privileged
from lib.secure_store import secure_write_json


NGINX_SITES_AVAILABLE = "/etc/nginx/sites-available"
NGINX_SITES_ENABLED = "/etc/nginx/sites-enabled"
NGINX_CONFIG_DIR = "/etc/nginx"
PROXY_CONFIG_FILE = "/etc/upcode-harbor/proxy_config.json"
CERTBOT_DIR = "/etc/letsencrypt"
MAX_ADVANCED_CONFIG_BYTES = 256_000


class ReverseProxyManager:
    """Manage Nginx reverse proxy configurations and SSL certificates."""
    
    def __init__(self):
        self.config_file = PROXY_CONFIG_FILE
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure necessary directories exist."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

    # RFC-1123 hostname / domain label: letters, digits, hyphens; dot-separated.
    # Wildcards (*.example.com) are intentionally excluded.
    _DOMAIN_RE = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    )
    # Backend host: IPv4 or a valid hostname (no port here — port is a separate int param)
    _HOST_RE = re.compile(
        r'^(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9]{1,63}'
        r'|(?:\d{1,3}\.){3}\d{1,3})$'
    )

    @classmethod
    def _validate_domain(cls, domain: str) -> None:
        """Raise ValueError if domain contains characters that could inject nginx config."""
        if not domain or not cls._DOMAIN_RE.match(domain):
            raise ValueError(
                f"Invalid domain {domain!r}. Only RFC-1123 hostnames are accepted "
                "(letters, digits, hyphens, dots; no wildcards or special characters)."
            )
        if len(domain) > 253:
            raise ValueError(f"Domain name too long: {len(domain)} chars (max 253).")

    @classmethod
    def _validate_host(cls, host: str) -> None:
        """Raise ValueError if backend_host contains characters that could inject nginx config."""
        if not host or not cls._HOST_RE.match(host):
            raise ValueError(
                f"Invalid backend host {host!r}. Must be an IPv4 address or hostname."
            )
    
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
        secure_write_json(self.config_file, config)
    
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
        backend_port: int = 9500,
        frontend_port: int = 9200,
        ssl_enabled: bool = False,
        force_ssl: bool = False
    ) -> Dict:
        """Create Nginx reverse proxy configuration."""
        self._validate_domain(domain)
        self._validate_host(backend_host)
        config_name = f"upcode_harbor_{domain.replace('.', '_')}"
        config_path = os.path.join(NGINX_SITES_AVAILABLE, config_name)
        try:
            require_privileged(
                "configure-nginx",
                domain,
                backend_host,
                str(backend_port),
                str(frontend_port),
                "1" if ssl_enabled else "0",
                "1" if force_ssl else "0",
                timeout=60,
            )
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
            log_proxy(f"Created proxy config for [{domain}] → {backend_host}:{backend_port} (SSL: {ssl_enabled})")
            
            return {
                "success": True,
                "message": "Proxy configuration created successfully",
                "config_path": config_path
            }
        except Exception as e:
            log_proxy(f"Failed to create proxy config for [{domain}]: {e}", error=True)
            return {"success": False, "message": str(e)}
    
    def _add_proxy_locations(self, config_lines: List[str], backend_host: str, backend_port: int, frontend_port: int):
        """Add proxy location blocks to config."""
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
        config_lines.append(f"        # Hide WWW-Authenticate to prevent browser auth popup")
        config_lines.append(f"        proxy_hide_header WWW-Authenticate;")
        config_lines.append(f"    }}")
        config_lines.append(f"")
        config_lines.append(f"    # WebSocket Support")
        config_lines.append(f"    location /ws/ {{")
        config_lines.append(f"        rewrite ^/ws/(.*)$ /$1 break;")
        config_lines.append(f"        proxy_pass http://{backend_host}:{backend_port};")
        config_lines.append(f"        proxy_http_version 1.1;")
        config_lines.append(f"        proxy_set_header Upgrade $http_upgrade;")
        config_lines.append(f"        proxy_set_header Connection \"upgrade\";")
        config_lines.append(f"        proxy_set_header Host $host;")
        config_lines.append(f"        proxy_set_header X-Real-IP $remote_addr;")
        config_lines.append(f"        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;")
        config_lines.append(f"        proxy_set_header X-Forwarded-Proto $scheme;")
        config_lines.append(f"        proxy_read_timeout 3600s;")
        config_lines.append(f"        proxy_send_timeout 3600s;")
        config_lines.append(f"    }}")
        config_lines.append(f"")
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
        self._validate_domain(domain)
        try:
            require_privileged("delete-nginx", domain, timeout=60)
            config = self._load_config()
            if domain in config:
                del config[domain]
                self._save_config(config)
            log_proxy(f"Deleted proxy config for [{domain}]")
            return {"success": True, "message": "Proxy configuration deleted"}
        except Exception as e:
            log_proxy(f"Failed to delete proxy config for [{domain}]: {e}", error=True)
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

    def _managed_nginx_config_path(self, domain: str) -> Path:
        """Return the derived Nginx path for an existing managed domain."""
        self._validate_domain(domain)
        if domain not in self._load_config():
            raise FileNotFoundError(f"No managed proxy configuration exists for {domain}")
        return Path(NGINX_SITES_AVAILABLE) / f"upcode_harbor_{domain.replace('.', '_')}"

    def get_advanced_proxy_config(self, domain: str) -> str:
        """Read one managed site configuration without following symlinks."""
        config_path = self._managed_nginx_config_path(domain)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(config_path, flags)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Managed Nginx configuration is not a regular file")
            if info.st_size > MAX_ADVANCED_CONFIG_BYTES:
                raise ValueError("Managed Nginx configuration exceeds the editor size limit")
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                data = handle.read(MAX_ADVANCED_CONFIG_BYTES + 1)
        finally:
            os.close(descriptor)
        if len(data) > MAX_ADVANCED_CONFIG_BYTES:
            raise ValueError("Managed Nginx configuration exceeds the editor size limit")
        return data.decode("utf-8")

    def update_advanced_proxy_config(self, domain: str, content: str) -> Dict:
        """Validate and atomically replace one managed Nginx site configuration."""
        self._managed_nginx_config_path(domain)
        if "\x00" in content:
            raise ValueError("Nginx configuration must not contain NUL bytes")
        if not content.endswith("\n"):
            content += "\n"
        data = content.encode("utf-8")
        if not data or len(data) > MAX_ADVANCED_CONFIG_BYTES:
            raise ValueError("Nginx configuration must be between 1 and 256000 bytes")

        staged_path = ""
        metadata = self._load_config()
        previous_settings = dict(metadata[domain])
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix="upcode-harbor-nginx-",
                suffix=".conf",
                delete=False,
            ) as staged:
                staged.write(content)
                staged_path = staged.name
            os.chmod(staged_path, 0o600)

            metadata[domain] = {**previous_settings, "advanced_override": True}
            self._save_config(metadata)
            try:
                require_privileged(
                    "replace-nginx-config",
                    domain,
                    staged_path,
                    timeout=60,
                )
            except Exception:
                metadata[domain] = previous_settings
                self._save_config(metadata)
                raise

            log_proxy(f"Updated advanced proxy config for [{domain}]")
            return {
                "success": True,
                "message": "Advanced proxy configuration updated successfully",
            }
        except Exception as error:
            log_proxy(
                f"Failed to update advanced proxy config for [{domain}]: {error}",
                error=True,
            )
            raise
        finally:
            if staged_path:
                try:
                    os.unlink(staged_path)
                except FileNotFoundError:
                    pass
    
    def obtain_certificate(self, domain: str, email: str, webroot: bool = False) -> Dict:
        """Obtain Let's Encrypt SSL certificate for domain."""
        self._validate_domain(domain)
        if not self.check_certbot_installed():
            return {"success": False, "message": "Certbot not installed"}
        
        try:
            webroot_path = "/var/www/html"
            os.makedirs(webroot_path, exist_ok=True)
            cmd = [
                "certbot", "certonly",
                "--webroot",
                "--webroot-path", webroot_path,
                "-d", domain,
                "--email", email,
                "--agree-tos",
                "--non-interactive"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                config = self._load_config()
                if domain in config:
                    config[domain]["ssl_enabled"] = True
                    self._save_config(config)
                    self.create_proxy_config(
                        domain=domain,
                        backend_host=config[domain]["backend_host"],
                        backend_port=config[domain]["backend_port"],
                        frontend_port=config[domain]["frontend_port"],
                        ssl_enabled=True,
                        force_ssl=config[domain].get("force_ssl", True)
                    )
                log_proxy(f"Obtained SSL certificate for [{domain}]")
                return {
                    "success": True,
                    "message": "Certificate obtained successfully",
                    "output": result.stdout
                }
            else:
                log_proxy(f"Failed to obtain SSL certificate for [{domain}]: {result.stderr.strip()}", error=True)
                return {
                    "success": False,
                    "message": f"Certificate request failed: {result.stderr}"
                }
        except Exception as e:
            log_proxy(f"Failed to obtain SSL certificate for [{domain}]: {e}", error=True)
            return {"success": False, "message": str(e)}
    
    def renew_certificates(self) -> Dict:
        """Renew all Let's Encrypt certificates."""
        if not self.check_certbot_installed():
            return {"success": False, "message": "Certbot not installed"}
        
        try:
            cmd = ["certbot", "renew", "--quiet"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                subprocess.run(["systemctl", "reload", "nginx"], capture_output=True)
                log_proxy("Renewed all SSL certificates")
                return {
                    "success": True,
                    "message": "Certificates renewed successfully"
                }
            else:
                log_proxy(f"Failed to renew SSL certificates: {result.stderr.strip()}", error=True)
                return {
                    "success": False,
                    "message": f"Renewal failed: {result.stderr}"
                }
        except Exception as e:
            log_proxy(f"Failed to renew SSL certificates: {e}", error=True)
            return {"success": False, "message": str(e)}
    
    def list_certificates(self) -> List[Dict]:
        """List all installed SSL certificates."""
        if not self.check_certbot_installed():
            return []
        
        try:
            cmd = ["certbot", "certificates"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
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
        self._validate_domain(domain)
        if not self.check_certbot_installed():
            return {"success": False, "message": "Certbot not installed"}
        
        try:
            cmd = ["certbot", "revoke", "--cert-name", domain, "--delete-after-revoke"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                config = self._load_config()
                if domain in config:
                    config[domain]["ssl_enabled"] = False
                    self._save_config(config)
                    self.create_proxy_config(
                        domain=domain,
                        backend_host=config[domain]["backend_host"],
                        backend_port=config[domain]["backend_port"],
                        frontend_port=config[domain]["frontend_port"],
                        ssl_enabled=False,
                        force_ssl=False
                    )
                log_proxy(f"Revoked SSL certificate for [{domain}]")
                return {
                    "success": True,
                    "message": "Certificate revoked successfully"
                }
            else:
                log_proxy(f"Failed to revoke SSL certificate for [{domain}]: {result.stderr.strip()}", error=True)
                return {
                    "success": False,
                    "message": f"Revocation failed: {result.stderr}"
                }
        except Exception as e:
            log_proxy(f"Failed to revoke SSL certificate for [{domain}]: {e}", error=True)
            return {"success": False, "message": str(e)}


reverse_proxy_manager = ReverseProxyManager()
