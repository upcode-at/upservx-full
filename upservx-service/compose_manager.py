"""
Docker Compose project management.
"""

import os
import yaml
import subprocess
import shutil
import re
from typing import List, Dict, Optional
from pathlib import Path

COMPOSE_BASE_DIR = "/opt/upservx/compose"


def normalize_project_name(name: str) -> str:
    """
    Normalize project name to be compatible with Docker Compose requirements.
    Must consist only of lowercase alphanumeric characters, hyphens, and underscores
    and must start with a letter or number.
    """
    # Convert to lowercase
    name = name.lower()
    
    # Replace spaces and invalid characters with hyphens
    name = re.sub(r'[^a-z0-9_-]', '-', name)
    
    # Remove leading/trailing hyphens or underscores
    name = name.strip('-_')
    
    # Ensure it starts with a letter or number
    if name and not name[0].isalnum():
        name = 'project-' + name
    
    # If empty after normalization, use default
    if not name:
        name = 'project'
    
    return name


class ComposeManager:
    """Manages Docker Compose projects and their files."""
    
    def __init__(self):
        """Initialize compose manager and ensure base directory exists."""
        os.makedirs(COMPOSE_BASE_DIR, exist_ok=True)
    
    def list_projects(self) -> List[Dict]:
        """List all compose projects with detailed service information."""
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
                            services_data = compose_data.get('services', {})
                            
                            # Extract detailed service information
                            services = []
                            for service_name, service_config in services_data.items():
                                service_details = self._extract_service_details(service_name, service_config)
                                services.append(service_details)
                            
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
    
    def _extract_service_details(self, service_name: str, service_config: Dict) -> Dict:
        """Extract detailed information from a service configuration."""
        details = {
            "name": service_name,
            "image": service_config.get("image", ""),
            "ports": [],
            "restart": service_config.get("restart", "no"),
            "volumes": [],
            "environment": {}
        }
        
        # Extract ports
        if "ports" in service_config:
            ports = service_config["ports"]
            if isinstance(ports, list):
                details["ports"] = ports
            elif isinstance(ports, dict):
                # Handle long syntax ports
                details["ports"] = list(ports.keys())
        
        # Extract volumes
        if "volumes" in service_config:
            volumes = service_config["volumes"]
            if isinstance(volumes, list):
                details["volumes"] = volumes
        
        # Extract environment
        if "environment" in service_config:
            env = service_config["environment"]
            if isinstance(env, list):
                for item in env:
                    if "=" in item:
                        key, value = item.split("=", 1)
                        details["environment"][key] = value
            elif isinstance(env, dict):
                details["environment"] = env
        
        return details
    
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
        # Normalize the project name
        original_name = project_name
        project_name = normalize_project_name(project_name)
        
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
            
            message = "Project created"
            if original_name != project_name:
                message = f"Project created as '{project_name}' (normalized from '{original_name}')"
            
            return {
                "success": True,
                "message": message,
                "path": project_dir,
                "project_name": project_name
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def add_service_to_project(self, project_name: str, service_config: Dict) -> Dict:
        """Add a service to a compose project."""
        # Normalize the project name
        project_name = normalize_project_name(project_name)
        
        project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        compose_file = os.path.join(project_dir, "docker-compose.yml")
        
        if not os.path.exists(project_dir):
            # Create project if it doesn't exist
            create_result = self.create_project(project_name)
            if not create_result["success"]:
                return create_result
            # Update project_name from the create result if it was normalized
            if "project_name" in create_result:
                project_name = create_result["project_name"]
        
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
        # Normalize the project name
        project_name = normalize_project_name(project_name)
        
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
    
    def get_service_details(self, project_name: str, service_name: str) -> Optional[Dict]:
        """Get detailed configuration of a specific service."""
        # Normalize the project name
        project_name = normalize_project_name(project_name)
        
        project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        compose_file = os.path.join(project_dir, "docker-compose.yml")
        
        if not os.path.exists(compose_file):
            return None
        
        try:
            with open(compose_file, 'r') as f:
                compose_data = yaml.safe_load(f)
            
            if service_name not in compose_data.get("services", {}):
                return None
            
            service_def = compose_data["services"][service_name]
            
            # Parse the service configuration
            result = {
                "name": service_name,
                "image": service_def.get("image", ""),
                "ports": service_def.get("ports", []),
                "volumes": service_def.get("volumes", []),
                "environment": service_def.get("environment", {}),
                "restart": service_def.get("restart", "unless-stopped"),
                "cpu": None,
                "memory": None
            }
            
            # Extract resource limits if present
            if "deploy" in service_def:
                resources = service_def.get("deploy", {}).get("resources", {}).get("limits", {})
                if "cpus" in resources:
                    result["cpu"] = float(resources["cpus"])
                if "memory" in resources:
                    # Parse memory string (e.g., "512M" -> 512)
                    mem_str = resources["memory"]
                    if mem_str.endswith("M"):
                        result["memory"] = int(mem_str[:-1])
                    elif mem_str.endswith("G"):
                        result["memory"] = int(mem_str[:-1]) * 1024
            
            return result
        except Exception as e:
            print(f"Error getting service details: {e}")
            return None
    
    def update_service_in_project(self, project_name: str, old_service_name: str, service_config: Dict) -> Dict:
        """Update an existing service in a compose project."""
        # Normalize the project name
        project_name = normalize_project_name(project_name)
        
        project_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        compose_file = os.path.join(project_dir, "docker-compose.yml")
        
        if not os.path.exists(compose_file):
            return {"success": False, "message": "Project not found"}
        
        try:
            # Load existing compose file
            with open(compose_file, 'r') as f:
                compose_data = yaml.safe_load(f) or {}
            
            if "services" not in compose_data:
                return {"success": False, "message": "No services in project"}
            
            # Check if old service exists
            if old_service_name not in compose_data["services"]:
                return {"success": False, "message": "Service not found"}
            
            # Build updated service configuration
            new_service_name = service_config.get("name", old_service_name)
            service_def = {
                "image": service_config.get("image"),
                "container_name": f"{project_name}_{new_service_name}"
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
            if service_config.get("restart"):
                service_def["restart"] = service_config["restart"]
            
            # Remove old service if name changed
            if old_service_name != new_service_name:
                del compose_data["services"][old_service_name]
            
            # Add/update service
            compose_data["services"][new_service_name] = service_def
            
            # Save compose file
            with open(compose_file, 'w') as f:
                yaml.dump(compose_data, f, default_flow_style=False, sort_keys=False)
            
            return {
                "success": True,
                "message": f"Service updated in project {project_name}",
                "compose_file": compose_file
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_project_compose(self, project_name: str) -> Optional[Dict]:
        """Get the compose file content for a project."""
        # Normalize the project name
        project_name = normalize_project_name(project_name)
        
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
        # Normalize the project name
        project_name = normalize_project_name(project_name)
        
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
        # Normalize the project name
        project_name = normalize_project_name(project_name)
        
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
        # Normalize the project name
        project_name = normalize_project_name(project_name)
        
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
        # Normalize the project name
        project_name = normalize_project_name(project_name)
        
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
