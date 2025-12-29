"""
App Store management for pre-configured Docker Compose applications.
"""

import os
import yaml
import shutil
import json
from typing import List, Dict, Optional
from pathlib import Path

# Directory where app templates are stored
APP_STORE_DIR = "/opt/upservx/app-store"
# Directory where user's compose projects are stored
COMPOSE_BASE_DIR = "/opt/upservx/compose"


class AppStore:
    """Manages app store templates and installations."""
    
    def __init__(self):
        """Initialize app store and ensure directories exist."""
        os.makedirs(APP_STORE_DIR, exist_ok=True)
        os.makedirs(COMPOSE_BASE_DIR, exist_ok=True)
    
    def list_apps(self) -> List[Dict]:
        """List all available apps in the store."""
        apps = []
        
        if not os.path.exists(APP_STORE_DIR):
            return apps
        
        for app_name in os.listdir(APP_STORE_DIR):
            app_dir = os.path.join(APP_STORE_DIR, app_name)
            if os.path.isdir(app_dir):
                metadata_file = os.path.join(app_dir, "app.json")
                compose_file = os.path.join(app_dir, "docker-compose.yml")
                
                if os.path.exists(metadata_file) and os.path.exists(compose_file):
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        
                        # Add installation status
                        installed = self._check_if_installed(app_name)
                        
                        # Check for icon image files (icon.png, logo.png, icon.jpg, logo.jpg)
                        icon = metadata.get("icon", "📦")
                        for icon_filename in ["icon.png", "logo.png", "icon.jpg", "logo.jpg"]:
                            icon_path = os.path.join(app_dir, icon_filename)
                            if os.path.exists(icon_path):
                                icon = f"/containers/app-store/apps/{app_name}/icon"
                                break
                        
                        apps.append({
                            "id": app_name,
                            "name": metadata.get("name", app_name),
                            "description": metadata.get("description", ""),
                            "version": metadata.get("version", "latest"),
                            "category": metadata.get("category", "other"),
                            "icon": icon,
                            "author": metadata.get("author", ""),
                            "ports": metadata.get("ports", []),
                            "volumes": metadata.get("volumes", []),
                            "installed": installed
                        })
                    except Exception as e:
                        print(f"Error loading app {app_name}: {e}")
        
        return sorted(apps, key=lambda x: x["name"])
    
    def get_app_details(self, app_id: str) -> Optional[Dict]:
        """Get detailed information about an app."""
        app_dir = os.path.join(APP_STORE_DIR, app_id)
        metadata_file = os.path.join(app_dir, "app.json")
        compose_file = os.path.join(app_dir, "docker-compose.yml")
        readme_file = os.path.join(app_dir, "README.md")
        
        if not os.path.exists(metadata_file) or not os.path.exists(compose_file):
            return None
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            with open(compose_file, 'r') as f:
                compose_content = f.read()
            
            readme_content = ""
            if os.path.exists(readme_file):
                with open(readme_file, 'r') as f:
                    readme_content = f.read()
            
            installed = self._check_if_installed(app_id)
            
            # Check for icon image files (icon.png, logo.png, icon.jpg, logo.jpg)
            icon = metadata.get("icon", "📦")
            for icon_filename in ["icon.png", "logo.png", "icon.jpg", "logo.jpg"]:
                icon_path = os.path.join(app_dir, icon_filename)
                if os.path.exists(icon_path):
                    icon = f"/containers/app-store/apps/{app_id}/icon"
                    break
            
            return {
                "id": app_id,
                "name": metadata.get("name", app_id),
                "description": metadata.get("description", ""),
                "version": metadata.get("version", "latest"),
                "category": metadata.get("category", "other"),
                "icon": icon,
                "author": metadata.get("author", ""),
                "ports": metadata.get("ports", []),
                "volumes": metadata.get("volumes", []),
                "environment": metadata.get("environment", {}),
                "compose_content": compose_content,
                "readme": readme_content,
                "installed": installed
            }
        except Exception as e:
            print(f"Error getting app details for {app_id}: {e}")
            return None
    
    def install_app(self, app_id: str, custom_name: Optional[str] = None) -> Dict:
        """Install an app from the store."""
        from compose_manager import normalize_project_name, compose_manager
        
        app_dir = os.path.join(APP_STORE_DIR, app_id)
        compose_file = os.path.join(app_dir, "docker-compose.yml")
        
        if not os.path.exists(compose_file):
            return {"success": False, "message": "App not found in store"}
        
        # Use custom name or default to app_id
        project_name = custom_name if custom_name else app_id
        project_name = normalize_project_name(project_name)
        
        # Check if already installed
        target_dir = os.path.join(COMPOSE_BASE_DIR, project_name)
        if os.path.exists(target_dir):
            return {"success": False, "message": f"Project '{project_name}' already exists"}
        
        try:
            # Copy the entire app directory to compose directory
            shutil.copytree(app_dir, target_dir)
            
            return {
                "success": True,
                "message": f"App installed as '{project_name}'",
                "project_name": project_name
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def uninstall_app(self, project_name: str) -> Dict:
        """Uninstall an app (removes the project)."""
        from compose_manager import compose_manager
        
        # Use compose manager's delete function
        return compose_manager.delete_project(project_name, remove_volumes=True)
    
    def _check_if_installed(self, app_id: str) -> bool:
        """Check if an app is currently installed."""
        # Check if a project with this app_id exists
        project_dir = os.path.join(COMPOSE_BASE_DIR, app_id)
        return os.path.exists(project_dir)
    
    def search_apps(self, query: str) -> List[Dict]:
        """Search for apps by name or description."""
        all_apps = self.list_apps()
        query_lower = query.lower()
        
        results = []
        for app in all_apps:
            if (query_lower in app["name"].lower() or 
                query_lower in app["description"].lower() or
                query_lower in app["category"].lower()):
                results.append(app)
        
        return results
    
    def get_categories(self) -> List[str]:
        """Get all unique categories."""
        apps = self.list_apps()
        categories = set()
        for app in apps:
            categories.add(app.get("category", "other"))
        return sorted(list(categories))
    
    def get_app_icon(self, app_id: str) -> Optional[str]:
        """Get the path to an app's icon file."""
        app_dir = os.path.join(APP_STORE_DIR, app_id)
        
        # Check for various icon file names
        for icon_filename in ["icon.png", "logo.png", "icon.jpg", "logo.jpg"]:
            icon_path = os.path.join(app_dir, icon_filename)
            if os.path.exists(icon_path):
                return icon_path
        
        return None


# Global instance
app_store = AppStore()
