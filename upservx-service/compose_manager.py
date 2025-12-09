"""
Docker Compose project management.
"""

import os
import yaml
import subprocess
import shutil
from typing import List, Dict, Optional
from pathlib import Path

COMPOSE_BASE_DIR = "/opt/upservx/compose"


class ComposeManager:
    """Manages Docker Compose projects and their files."""
    
    def __init__(self):
        """Initialize compose manager and ensure base directory exists."""
        os.makedirs(COMPOSE_BASE_DIR, exist_ok=True)
    
    def list_projects(self) -> List[Dict]:
        """List all compose projects."""
        projects = []
        
        if not os.path.exists(COMPOSE_BASE_DIR):
            return projects
        
        for project_name in os.listdir(COMPOSE_BASE_DIR):
            project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
            if os.path.isdir(project_dir):
                compose_file = os.path.join(project_dir, "docker-compose.yml")
                
                if os.path.exists(compose_file):
                    try:
                        with open(compose_file, 'r') as f:
                            compose_data = yaml.safe_load(f)
                            services = list(compose_data.get('services', {}).keys())
                            
                            # Get running status
                            status = self._get_project_status(project_name, project_dir)
                            
                            projects.append({
                                "name": project_name,
                                "path": project_dir,
                                "services": services,
                                "service_count": len(services),
                                "status": status
                            })
                    except Exception as e:
                        projects.append({
                            "name": project_name,
                            "path": project_dir,
                            "services": [],
                            "service_count": 0,
                            "status": "error",
                            "error": str(e)
                        })
        
        return projects
    
    def _get_project_status(self, project_name: str, project_dir: str) -> str:
        """Get the status of a compose project."""
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", os.path.join(project_dir, "docker-compose.yml"), "-p", project_name, "ps", "-q"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                container_ids = result.stdout.strip().split('\n')
                if container_ids and container_ids[0]:
                    # Check if any containers are running
                    for cid in container_ids:
                        if cid.strip():
                            inspect = subprocess.run(
                                ["docker", "inspect", "-f", "{{.State.Running}}", cid.strip()],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            if inspect.returncode == 0 and "true" in inspect.stdout:
                                return "running"
                    return "stopped"
            return "stopped"
        except Exception:
            return "unknown"
    
    def create_project(self, project_name: str) -> Dict:
        """Create a new compose project directory."""
        project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        
        if os.path.exists(project_dir):
            return {"success": False, "message": "Project already exists"}
        
        try:
            os.makedirs(project_dir, exist_ok=True)
            
            # Create empty compose file
            compose_file = os.path.join(project_dir, "docker-compose.yml")
            compose_data = {
                "version": "3.8",
                "services": {}
            }
            
            with open(compose_file, 'w') as f:
                yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
            
            return {
                "success": True,
                "message": "Project created",
                "path": project_dir
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def add_service_to_project(self, project_name: str, service_config: Dict) -> Dict:
        """Add a service to a compose project."""
        project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        compose_file = os.path.join(project_dir, "docker-compose.yml")
        
        if not os.path.exists(project_dir):
            # Create project if it doesn't exist
            create_result = self.create_project(project_name)
            if not create_result["success"]:
                return create_result
        
        try:
            # Load existing compose file
            if os.path.exists(compose_file):
                with open(compose_file, 'r') as f:
                    compose_data = yaml.safe_load(f) or {}
            else:
                compose_data = {"version": "3.8", "services": {}}
            
            if "services" not in compose_data:
                compose_data["services"] = {}
            
            # Build service configuration
            service_name = service_config.get("name")
            service_def = {
                "image": service_config.get("image"),
                "container_name": f"{project_name}_{service_name}"
            }
            
            # Add ports
            if service_config.get("ports"):
                service_def["ports"] = service_config["ports"]
            
            # Add volumes
            if service_config.get("volumes"):
                service_def["volumes"] = service_config["volumes"]
            
            # Add environment variables
            if service_config.get("environment"):
                service_def["environment"] = service_config["environment"]
            
            # Add resource limits
            if service_config.get("cpu") or service_config.get("memory"):
                service_def["deploy"] = {"resources": {"limits": {}}}
                if service_config.get("cpu"):
                    service_def["deploy"]["resources"]["limits"]["cpus"] = str(service_config["cpu"])
                if service_config.get("memory"):
                    service_def["deploy"]["resources"]["limits"]["memory"] = f"{service_config['memory']}M"
            
            # Add restart policy
            service_def["restart"] = service_config.get("restart", "unless-stopped")
            
            # Add to compose
            compose_data["services"][service_name] = service_def
            
            # Write back
            with open(compose_file, 'w') as f:
                yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
            
            return {
                "success": True,
                "message": f"Service {service_name} added to project {project_name}",
                "compose_file": compose_file
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def remove_service_from_project(self, project_name: str, service_name: str) -> Dict:
        """Remove a service from a compose project."""
        project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        compose_file = os.path.join(project_dir, "docker-compose.yml")
        
        if not os.path.exists(compose_file):
            return {"success": False, "message": "Project not found"}
        
        try:
            with open(compose_file, 'r') as f:
                compose_data = yaml.safe_load(f)
            
            if service_name in compose_data.get("services", {}):
                del compose_data["services"][service_name]
                
                with open(compose_file, 'w') as f:
                    yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
                
                return {
                    "success": True,
                    "message": f"Service {service_name} removed from project {project_name}"
                }
            else:
                return {"success": False, "message": "Service not found"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_project_compose(self, project_name: str) -> Optional[Dict]:
        """Get the compose file content for a project."""
        project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        compose_file = os.path.join(project_dir, "docker-compose.yml")
        
        if not os.path.exists(compose_file):
            return None
        
        try:
            with open(compose_file, 'r') as f:
                return yaml.safe_load(f)
        except Exception:
            return None
    
    def update_project_compose(self, project_name: str, compose_content: str) -> Dict:
        """Update compose file content directly."""
        project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        compose_file = os.path.join(project_dir, "docker-compose.yml")
        
        if not os.path.exists(project_dir):
            os.makedirs(project_dir, exist_ok=True)
        
        try:
            # Validate YAML
            yaml.safe_load(compose_content)
            
            with open(compose_file, 'w') as f:
                f.write(compose_content)
            
            return {
                "success": True,
                "message": "Compose file updated"
            }
        except yaml.YAMLError as e:
            return {"success": False, "message": f"Invalid YAML: {str(e)}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def start_project(self, project_name: str) -> Dict:
        """Start all services in a compose project."""
        project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        compose_file = os.path.join(project_dir, "docker-compose.yml")
        
        if not os.path.exists(compose_file):
            return {"success": False, "message": "Project not found"}
        
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", compose_file, "-p", project_name, "up", "-d"],
                capture_output=True,
                text=True,
                cwd=project_dir
            )
            
            if result.returncode == 0:
                return {"success": True, "message": "Project started", "output": result.stdout}
            else:
                return {"success": False, "message": result.stderr or "Failed to start"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def stop_project(self, project_name: str) -> Dict:
        """Stop all services in a compose project."""
        project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        compose_file = os.path.join(project_dir, "docker-compose.yml")
        
        if not os.path.exists(compose_file):
            return {"success": False, "message": "Project not found"}
        
        try:
            result = subprocess.run(
                ["docker", "compose", "-f", compose_file, "-p", project_name, "stop"],
                capture_output=True,
                text=True,
                cwd=project_dir
            )
            
            if result.returncode == 0:
                return {"success": True, "message": "Project stopped"}
            else:
                return {"success": False, "message": result.stderr or "Failed to stop"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def delete_project(self, project_name: str, remove_volumes: bool = True) -> Dict:
        """Delete a compose project."""
        project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        compose_file = os.path.join(project_dir, "docker-compose.yml")
        
        if not os.path.exists(project_dir):
            return {"success": False, "message": "Project not found"}
        
        try:
            # Stop and remove containers
            if os.path.exists(compose_file):
                cmd = ["docker", "compose", "-f", compose_file, "-p", project_name, "down"]
                if remove_volumes:
                    cmd.append("-v")
                
                subprocess.run(cmd, capture_output=True, cwd=project_dir)
            
            # Remove project directory
            shutil.rmtree(project_dir)
            
            return {"success": True, "message": "Project deleted"}
        except Exception as e:
            return {"success": False, "message": str(e)}


# Global instance
compose_manager = ComposeManager()
