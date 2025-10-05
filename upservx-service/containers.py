"""
Container management utilities for Docker, LXC, and Kubernetes.
"""

import subprocess
import json
import shutil
from typing import List
from datetime import datetime
from models import Container, ContainerImageInfo


# Containers that are created via the API are stored here in-memory. Containers
# discovered from Docker, LXC or Kubernetes are queried on demand and not stored
# in this list.
containers: List[Container] = []
next_container_id = 1


def _parse_ports(port_str: str) -> List[str]:
    """Split Docker style port mappings into a list."""
    if not port_str:
        return []
    return [p.strip() for p in port_str.split(',') if p.strip()]


def get_docker_containers() -> List[Container]:
    """Return running Docker containers using the docker CLI."""
    if shutil.which("docker") is None:
        return []
    try:
        output = subprocess.check_output(
            [
                "docker",
                "ps",
                "-a",
                "--format",
                "{{.Names}}||{{.Image}}||{{.Status}}||{{.Ports}}||{{.RunningFor}}",
            ],
            text=True,
        ).strip()
    except Exception:
        return []

    containers_list = []
    for line in output.splitlines():
        parts = line.split("||")
        if len(parts) != 5:
            continue
        name, image, status, ports, running_for = parts
        containers_list.append(
            Container(
                id=0,
                name=name,
                type="Docker",
                status="running" if status.lower().startswith("up") else "stopped",
                image=image,
                ports=_parse_ports(ports),
                mounts=[],
                envs=[],
                cpu=0.0,
                memory=0,
                created=running_for,
            )
        )
    return containers_list


def get_lxc_containers() -> List[Container]:
    """Return LXC/LXD containers using the lxc CLI if available."""
    if shutil.which("lxc") is None:
        return []
    try:
        output = subprocess.check_output(
            ["lxc", "list", "--format", "json"], text=True
        ).strip()
        data = json.loads(output)
    except Exception:
        return []

    containers_list = []
    for item in data:
        config = item.get("config", {})
        os_name = config.get("image.os", "")
        release = config.get("image.release", "")
        image = f"{os_name} {release}".strip()
        containers_list.append(
            Container(
                id=0,
                name=item.get("name", ""),
                type="LXC",
                status=item.get("status", "").lower(),
                image=image,
                ports=[],
                mounts=[],
                envs=[],
                cpu=0.0,
                memory=0,
                created=item.get("created_at", ""),
            )
        )
    return containers_list


def get_k8s_pods() -> List[Container]:
    """Return Kubernetes pods using kubectl if available."""
    if shutil.which("kubectl") is None:
        return []
    try:
        output = subprocess.check_output(
            ["kubectl", "get", "pods", "-A", "-o", "json"], text=True
        ).strip()
        data = json.loads(output)
    except Exception:
        return []

    containers_list = []
    for item in data.get("items", []):
        metadata = item.get("metadata", {})
        status = item.get("status", {})
        containers_list.append(
            Container(
                id=0,
                name=metadata.get("name", ""),
                type="Kubernetes",
                status=status.get("phase", "").lower(),
                image="",
                ports=[],
                mounts=[],
                envs=[],
                cpu=0.0,
                memory=0,
                created=metadata.get("creationTimestamp", ""),
            )
        )
    return containers_list


def get_docker_images() -> List[str]:
    """Return available Docker images using the docker CLI."""
    if shutil.which("docker") is None:
        return []
    try:
        output = subprocess.check_output(
            ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
            text=True,
        ).strip()
    except Exception:
        return []
    images = [line for line in output.splitlines() if line and not line.startswith("<none>")]
    return images


def _parse_docker_size(size: str) -> float:
    """Parse Docker image size string into MB."""
    size = size.lower().strip()
    if size.endswith("gb"):
        try:
            return float(size[:-2].strip()) * 1000
        except ValueError:
            return 0.0
    if size.endswith("mb"):
        try:
            return float(size[:-2].strip())
        except ValueError:
            return 0.0
    return 0.0


def get_docker_image_details() -> List[ContainerImageInfo]:
    """Return detailed information about Docker images."""
    if shutil.which("docker") is None:
        return []
    try:
        output = subprocess.check_output(
            [
                "docker",
                "images",
                "--format",
                "{{.Repository}}||{{.Tag}}||{{.ID}}||{{.Size}}||{{.CreatedSince}}",
            ],
            text=True,
        ).strip()
    except Exception:
        return []
    images: List[ContainerImageInfo] = []
    for idx, line in enumerate(output.splitlines(), start=1):
        parts = line.split("||")
        if len(parts) != 5:
            continue
        repo, tag, image_id, size, created = parts
        images.append(
            ContainerImageInfo(
                id=idx,
                repository=repo,
                tag=tag,
                imageId=image_id,
                size=_parse_docker_size(size),
                created=created,
                used=True,
                pulls=0,
            )
        )
    return images


def get_lxc_image_details() -> List[ContainerImageInfo]:
    """Return detailed information about LXC images."""
    if shutil.which("lxc") is None:
        return []
    try:
        output = subprocess.check_output(["lxc", "image", "list", "--format", "json"], text=True).strip()
        data = json.loads(output)
    except Exception:
        return []
    images: List[ContainerImageInfo] = []
    for idx, img in enumerate(data, start=1):
        alias = ""
        aliases = img.get("aliases", [])
        if aliases:
            alias = aliases[0].get("name", "")
        repository = alias
        tag = ""
        if "/" in alias:
            repository, tag = alias.split("/", 1)
        images.append(
            ContainerImageInfo(
                id=idx,
                repository=repository,
                tag=tag,
                imageId=img.get("fingerprint", ""),
                size=round(img.get("size", 0) / (1024 ** 2), 2),
                created=img.get("uploaded_at", ""),
                used=False,
                pulls=0,
            )
        )
    return images


def get_lxc_images() -> List[str]:
    """Return available LXC images using the lxc CLI."""
    if shutil.which("lxc") is None:
        return []
    try:
        output = subprocess.check_output(["lxc", "image", "list", "--format", "json"], text=True).strip()
        data = json.loads(output)
    except Exception:
        return []

    images = []
    for img in data:
        aliases = img.get("aliases", [])
        if aliases:
            images.append(aliases[0].get("name", ""))
        else:
            images.append(img.get("fingerprint", ""))
    return images


def find_container_type(name: str) -> str | None:
    """Detect which container backend knows a container by this name."""
    for c in get_docker_containers():
        if c.name == name:
            return "docker"
    for c in get_lxc_containers():
        if c.name == name:
            return "lxc"
    for c in get_k8s_pods():
        if c.name == name:
            return "k8s"
    for c in containers:
        if c.name == name:
            return "api"
    return None


def list_all_containers() -> List[Container]:
    """Return all containers from all backends."""
    all_containers: List[Container] = []
    all_containers.extend(get_docker_containers())
    all_containers.extend(get_lxc_containers())
    all_containers.extend(get_k8s_pods())
    all_containers.extend(containers)

    # Assign stable sequential ids for the response
    for idx, c in enumerate(all_containers, start=1):
        c.id = idx
    return all_containers


def create_api_container(container_data: dict) -> Container:
    """Create a new container in the in-memory API storage."""
    global next_container_id
    container = Container(
        id=next_container_id,
        name=container_data["name"],
        type=container_data["type"],
        status="running",
        image=container_data["image"],
        ports=container_data.get("ports", []),
        mounts=container_data.get("mounts", []),
        envs=container_data.get("envs", []),
        cpu=container_data.get("cpu", 0.0),
        memory=container_data.get("memory", 0),
        created=datetime.utcnow().date().isoformat(),
    )
    next_container_id += 1
    containers.append(container)
    return container