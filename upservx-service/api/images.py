"""
API routes for image management.
"""

from fastapi import APIRouter, HTTPException
import subprocess
import shutil
from models import ImagePullRequest
from containers import (
    get_docker_images, get_lxc_images,
    get_docker_image_details, get_lxc_image_details
)
from upservx_logger import log_container

router = APIRouter(prefix="/images")


@router.get("")
def list_images(type: str, full: bool = False):
    """Return available container images for the given type."""
    type_lower = type.lower()
    
    if full:
        if type_lower in {"docker", "kubernetes"}:
            return {"images": [img.dict() for img in get_docker_image_details()]}
        if type_lower == "lxc":
            return {"images": [img.dict() for img in get_lxc_image_details()]}
    else:
        if type_lower in {"docker", "kubernetes"}:
            return {"images": get_docker_images()}
        if type_lower == "lxc":
            return {"images": get_lxc_images()}
    
    raise HTTPException(status_code=400, detail="unknown container type")


@router.post("/pull")
def pull_image(payload: ImagePullRequest):
    """Pull a container image via Docker or LXC."""
    if not payload.image:
        raise HTTPException(status_code=400, detail="image required")

    typ = (payload.type or "docker").lower()
    
    if typ in {"docker", "kubernetes"}:
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        
        image = payload.image
        if payload.registry:
            image = f"{payload.registry}/{image}"
        
        result = subprocess.run(["docker", "pull", image], capture_output=True, text=True)
        if result.returncode != 0:
            log_container(f"Failed to pull Docker image [{image}]: {result.stderr.strip()}", error=True)
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to pull")
        
        log_container(f"Pulled Docker image [{image}]")
        return {"detail": "pulled"}
    
    if typ == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        
        remote = payload.registry or "images"
        alias = payload.image.split("/")[0]
        
        result = subprocess.run([
            "lxc", "image", "copy", f"{remote}:{payload.image}",
            "local:", "--alias", alias,
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            log_container(f"Failed to pull LXC image [{payload.image}] from [{remote}]: {result.stderr.strip()}", error=True)
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to pull")
        
        log_container(f"Pulled LXC image [{payload.image}] from [{remote}]")
        return {"detail": "pulled"}
    
    raise HTTPException(status_code=400, detail="unknown container type")


@router.delete("/{image}")
def delete_image(image: str, type: str):
    """Delete a container image."""
    type_lower = type.lower()
    
    if type_lower in {"docker", "kubernetes"}:
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        
        result = subprocess.run(["docker", "rmi", image], capture_output=True, text=True)
        if result.returncode != 0:
            log_container(f"Failed to delete Docker image [{image}]: {result.stderr.strip()}", error=True)
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
        
        log_container(f"Deleted Docker image [{image}]")
        return {"detail": "deleted"}
    
    if type_lower == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        
        result = subprocess.run(["lxc", "image", "delete", image], capture_output=True, text=True)
        if result.returncode != 0:
            log_container(f"Failed to delete LXC image [{image}]: {result.stderr.strip()}", error=True)
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
        
        log_container(f"Deleted LXC image [{image}]")
        return {"detail": "deleted"}
    
    raise HTTPException(status_code=400, detail="unknown container type")