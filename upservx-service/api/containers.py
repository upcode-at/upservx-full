"""
API routes for container management.
"""

from fastapi import APIRouter, HTTPException, WebSocket
from starlette.websockets import WebSocketDisconnect
from typing import List
import subprocess
import shutil
import asyncio
import pty
import os
import fcntl
from datetime import datetime

from models import ContainerCreate, Container, ImagePullRequest
from containers import (
    list_all_containers, get_docker_images, get_lxc_images,
    get_docker_image_details, get_lxc_image_details,
    find_container_type, create_api_container
)

router = APIRouter(prefix="/containers")


@router.get("")
def list_containers():
    """List all containers from all backends."""
    all_containers = list_all_containers()
    return [c.dict() for c in all_containers]


@router.post("")
def create_container(payload: ContainerCreate):
    """Create a new container via Docker, LXC or Kubernetes if available."""
    typ = payload.type.lower()
    
    if typ == "docker":
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        
        cmd = ["docker", "run", "-d", "--name", payload.name]
        for p in payload.ports:
            cmd.extend(["-p", p])
        for m in payload.mounts:
            cmd.extend(["-v", m])
        for e in payload.envs:
            cmd.extend(["-e", e])
        cmd.append(payload.image)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")
        
        # Fetch fresh info about the new container
        from containers import get_docker_containers
        container_list = [c for c in get_docker_containers() if c.name == payload.name]
        return container_list[0].dict() if container_list else {"detail": "created"}

    elif typ == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        
        try:
            result = subprocess.run(["lxc", "launch", payload.image, payload.name], capture_output=True, text=True)
            if result.returncode != 0:
                raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")
        except HTTPException as exc:
            if "Failed getting root disk" in str(exc.detail):
                result = subprocess.run(["lxc", "init", payload.image, payload.name], capture_output=True, text=True)
                if result.returncode != 0:
                    raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")
            else:
                raise
        
        from containers import get_lxc_containers
        container_list = [c for c in get_lxc_containers() if c.name == payload.name]
        return container_list[0].dict() if container_list else {"detail": "created"}

    elif typ == "kubernetes":
        if shutil.which("kubectl") is None:
            raise HTTPException(status_code=404, detail="kubectl not installed")
        
        result = subprocess.run(["kubectl", "run", payload.name, "--image", payload.image, "--restart=Never"], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create")
        
        from containers import get_k8s_pods
        pods = [c for c in get_k8s_pods() if c.name == payload.name]
        return pods[0].dict() if pods else {"detail": "created"}

    else:
        # Fallback to in-memory creation for unknown types
        container = create_api_container(payload.dict())
        return container.dict()


@router.post("/{name}/start")
def start_container(name: str):
    """Start a container by name if possible."""
    ctype = find_container_type(name)
    
    if ctype == "docker":
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        result = subprocess.run(["docker", "start", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to start")
    
    elif ctype == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        result = subprocess.run(["lxc", "start", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to start")
    
    elif ctype == "k8s":
        if shutil.which("kubectl") is None:
            raise HTTPException(status_code=404, detail="kubectl not installed")
        result = subprocess.run(["kubectl", "scale", "--replicas=1", f"deployment/{name}"], capture_output=True, text=True)
        if result.returncode != 0:
            result = subprocess.run(["kubectl", "scale", "--replicas=1", f"statefulset/{name}"], capture_output=True, text=True)
            if result.returncode != 0:
                raise HTTPException(status_code=400, detail="failed to start")
    
    elif ctype == "api":
        from containers import containers
        for c in containers:
            if c.name == name:
                c.status = "running"
                break
    else:
        raise HTTPException(status_code=404, detail="container not found")
    
    return {"detail": "started"}


@router.post("/{name}/stop")
def stop_container(name: str):
    """Stop a container by name if possible."""
    ctype = find_container_type(name)
    
    if ctype == "docker":
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        result = subprocess.run(["docker", "stop", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to stop")
    
    elif ctype == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        result = subprocess.run(["lxc", "stop", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to stop")
    
    elif ctype == "k8s":
        if shutil.which("kubectl") is None:
            raise HTTPException(status_code=404, detail="kubectl not installed")
        result = subprocess.run(["kubectl", "scale", "--replicas=0", f"deployment/{name}"], capture_output=True, text=True)
        if result.returncode != 0:
            result = subprocess.run(["kubectl", "scale", "--replicas=0", f"statefulset/{name}"], capture_output=True, text=True)
            if result.returncode != 0:
                raise HTTPException(status_code=400, detail="failed to stop")
    
    elif ctype == "api":
        from containers import containers
        for c in containers:
            if c.name == name:
                c.status = "stopped"
                break
    else:
        raise HTTPException(status_code=404, detail="container not found")
    
    return {"detail": "stopped"}


@router.delete("/{name}")
def delete_container(name: str):
    """Delete a container by name if possible."""
    ctype = find_container_type(name)
    
    if ctype == "docker":
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        result = subprocess.run(["docker", "rm", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
    
    elif ctype == "lxc":
        if shutil.which("lxc") is None:
            raise HTTPException(status_code=404, detail="lxc not installed")
        result = subprocess.run(["lxc", "delete", "--force", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
    
    elif ctype == "k8s":
        if shutil.which("kubectl") is None:
            raise HTTPException(status_code=404, detail="kubectl not installed")
        result = subprocess.run(["kubectl", "delete", "pod", name], capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete")
    
    elif ctype == "api":
        from containers import containers
        containers[:] = [c for c in containers if c.name != name]
    else:
        raise HTTPException(status_code=404, detail="container not found")
    
    return {"detail": "deleted"}


@router.websocket("/{name}/terminal")
async def container_terminal(websocket: WebSocket, name: str):
    """Provide interactive shell access to a container via websocket."""
    await websocket.accept()
    ctype = find_container_type(name)
    
    if ctype == "docker":
        if shutil.which("docker") is None:
            await websocket.send_text("Docker not installed")
            await websocket.close()
            return
        cmd = [
            "docker", "exec", "-it", name, "/bin/sh", "-c",
            "if [ -x /bin/bash ]; then exec /bin/bash -i; else exec /bin/sh -i; fi",
        ]
    
    elif ctype == "lxc":
        if shutil.which("lxc") is None:
            await websocket.send_text("LXC not installed")
            await websocket.close()
            return
        cmd = [
            "lxc", "exec", name, "--mode", "interactive", "--", "/bin/sh", "-c",
            "if [ -x /bin/bash ]; then exec /bin/bash -i; else exec /bin/sh -i; fi",
        ]
    
    elif ctype == "k8s":
        if shutil.which("kubectl") is None:
            await websocket.send_text("kubectl not installed")
            await websocket.close()
            return
        cmd = [
            "kubectl", "exec", "-it", name, "--", "/bin/sh", "-c",
            "if [ -x /bin/bash ]; then exec /bin/bash -i; else exec /bin/sh -i; fi",
        ]
    else:
        await websocket.close()
        return

    env = dict(os.environ)
    env["PS1"] = r"\\u@\\h:\\w$ "
    env["TERM"] = "xterm"

    master_fd, slave_fd = pty.openpty()
    
    # Make master_fd non-blocking
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=env,
        preexec_fn=os.setsid,
    )
    os.close(slave_fd)

    async def read_output():
        try:
            while process.returncode is None:
                try:
                    data = os.read(master_fd, 1024)
                    if data:
                        await websocket.send_text(data.decode('utf-8', errors='ignore'))
                except (OSError, BlockingIOError):
                    # No data available
                    await asyncio.sleep(0.01)
                except WebSocketDisconnect:
                    break
                except Exception:
                    break
        except Exception:
            pass
        finally:
            try:
                os.close(master_fd)
            except:
                pass

    async def read_input():
        try:
            while process.returncode is None:
                try:
                    data = await websocket.receive_text()
                    if data:
                        os.write(master_fd, data.encode('utf-8'))
                except WebSocketDisconnect:
                    break
                except Exception:
                    break
        except Exception:
            pass
        finally:
            if process.returncode is None:
                try:
                    process.terminate()
                    await process.wait()
                except:
                    pass

    try:
        # Run both tasks and handle disconnection gracefully
        done, pending = await asyncio.wait(
            [asyncio.create_task(read_output()), asyncio.create_task(read_input())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel any pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
    except Exception:
        pass
    finally:
        # Clean up process if still running
        if process.returncode is None:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except:
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass