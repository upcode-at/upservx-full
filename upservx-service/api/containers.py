"""
API routes for container management.
"""

from fastapi import APIRouter, HTTPException, WebSocket, File, UploadFile, Request
from starlette.websockets import WebSocketDisconnect
from typing import List
import subprocess
import shutil
import asyncio
import pty
import os
import fcntl
import json
from datetime import datetime

from models import ContainerCreate, Container, ImagePullRequest
from containers import (
    list_all_containers, get_docker_images, get_lxc_images,
    get_docker_image_details, get_lxc_image_details,
    find_container_type, create_api_container
)
from fastapi.responses import StreamingResponse
import tempfile
import tarfile
import shutil
from fastapi import File, UploadFile
import tempfile
import tarfile
import shutil
from compose_manager import compose_manager
from app_store import app_store
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/containers")


# Compose Manager Models
class ComposeServiceCreate(BaseModel):
    name: str
    image: str
    ports: Optional[List[str]] = None
    volumes: Optional[List[str]] = None
    environment: Optional[dict] = None
    cpu: Optional[float] = None
    memory: Optional[int] = None
    restart: Optional[str] = "unless-stopped"

class ComposeProjectInfo(BaseModel):
    project_name: str


@router.get("")
def list_containers(include_compose: bool = False):
    """List all containers from all backends."""
    all_containers = list_all_containers(include_compose=include_compose)
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


@router.get("/{name}/logs")
def get_container_logs(name: str, lines: int = 100):
    """Get logs from a Docker container."""
    ctype = find_container_type(name)
    
    if ctype == "docker":
        if shutil.which("docker") is None:
            raise HTTPException(status_code=404, detail="docker not installed")
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), name],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to get logs")
        
        # Combine stdout and stderr
        logs = result.stdout + result.stderr
        return {"logs": logs}
    
    else:
        raise HTTPException(status_code=400, detail="logs only available for docker containers")


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


@router.post("/build")
def build_docker_image(request: Request, image: str, tag: str = "latest", dockerfile: UploadFile = File(None), context: UploadFile = File(None)):
    """Build a Docker image from an uploaded Dockerfile or a context tarball.

    - If `context` (tar.gz or tar) is provided, it will be extracted and used as build context.
    - If `dockerfile` is provided, it will be written to a temporary directory as `Dockerfile` and used as build context.
    Returns build logs on success or error details.
    """
    print("[containers.build] incoming request", request.method, request.url)
    try:
        print("[containers.build] headers:", dict(request.headers))
    except Exception:
        pass

    if shutil.which("docker") is None:
        raise HTTPException(status_code=404, detail="docker not installed")

    if not dockerfile and not context:
        raise HTTPException(status_code=400, detail="dockerfile or context required")

    tempdir = tempfile.mkdtemp(prefix="docker_build_")
    try:
        # Prepare context
        if context:
            # save uploaded tar to temp and extract
            ctx_path = os.path.join(tempdir, "context.tar")
            with open(ctx_path, "wb") as f:
                f.write(context.file.read())
            try:
                with tarfile.open(ctx_path) as tar:
                    tar.extractall(path=tempdir)
            except tarfile.ReadError:
                # not a tar - maybe plain directory stream
                pass
        if dockerfile:
            df_path = os.path.join(tempdir, "Dockerfile")
            with open(df_path, "wb") as f:
                f.write(dockerfile.file.read())

        # Build command
        tag_name = f"{image}:{tag}" if tag else image
        cmd = ["docker", "build", "-t", tag_name, tempdir]

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out_lines = []
        for line in proc.stdout:
            out_lines.append(line)
        proc.wait()
        logs = "".join(out_lines)
        if proc.returncode != 0:
            raise HTTPException(status_code=400, detail=logs or "build failed")

        return {"detail": "built", "image": tag_name, "logs": logs}
    finally:
        try:
            shutil.rmtree(tempdir)
        except Exception:
            pass



@router.post("/build/stream")
def build_docker_image_stream(request: Request, image: str, tag: str = "latest", dockerfile: UploadFile = File(None), context: UploadFile = File(None)):
    """Stream docker build logs as plain text (chunked) in the response body.
    The client can read the response body as a stream and append logs in real time.
    """
    print("[containers.build.stream] incoming request", request.method, request.url)
    try:
        print("[containers.build.stream] headers:", dict(request.headers))
    except Exception:
        pass

    if shutil.which("docker") is None:
        raise HTTPException(status_code=404, detail="docker not installed")

    if not dockerfile and not context:
        raise HTTPException(status_code=400, detail="dockerfile or context required")

    tempdir = tempfile.mkdtemp(prefix="docker_build_")
    # Read uploaded files into memory here so they remain available inside the
    # streaming generator (UploadFile.file may be closed after request handling).
    dockerfile_bytes = None
    context_bytes = None
    try:
        if context:
            context.file.seek(0)
            context_bytes = context.file.read()
            try:
                context.file.close()
            except Exception:
                pass
        if dockerfile:
            dockerfile.file.seek(0)
            dockerfile_bytes = dockerfile.file.read()
            try:
                dockerfile.file.close()
            except Exception:
                pass
    except Exception:
        # if reading fails, continue and let generator handle missing files
        pass

    def generate():
        try:
            # prepare
            if context_bytes:
                ctx_path = os.path.join(tempdir, "context.tar")
                with open(ctx_path, "wb") as f:
                    f.write(context_bytes)
                try:
                    with tarfile.open(ctx_path) as tar:
                        tar.extractall(path=tempdir)
                except tarfile.ReadError:
                    pass
            if dockerfile_bytes:
                df_path = os.path.join(tempdir, "Dockerfile")
                with open(df_path, "wb") as f:
                    f.write(dockerfile_bytes)

            tag_name = f"{image}:{tag}" if tag else image
            cmd = ["docker", "build", "-t", tag_name, tempdir]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True)
            try:
                for line in proc.stdout:
                    yield line
                proc.wait()
                if proc.returncode != 0:
                    yield f"\nBUILD FAILED with code {proc.returncode}\n"
                else:
                    yield f"\nBUILD FINISHED: {tag_name}\n"
            finally:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
        finally:
            try:
                shutil.rmtree(tempdir)
            except Exception:
                pass

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


# Docker Compose endpoints
@router.post("/compose")
async def create_compose_stack(
    project_name: str,
    compose_file: UploadFile = File(...)
):
    """Create a Docker Compose stack from an uploaded docker-compose.yml file."""
    if shutil.which("docker") is None:
        raise HTTPException(status_code=404, detail="docker not installed")
    
    # Create temporary directory for compose file
    temp_dir = tempfile.mkdtemp()
    compose_path = os.path.join(temp_dir, "docker-compose.yml")
    
    try:
        # Save uploaded compose file
        content = await compose_file.read()
        with open(compose_path, "wb") as f:
            f.write(content)
        
        # Run docker compose up
        result = subprocess.run(
            ["docker", "compose", "-f", compose_path, "-p", project_name, "up", "-d"],
            capture_output=True,
            text=True,
            cwd=temp_dir
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to create compose stack")
        
        return {"detail": "Compose stack created", "project": project_name, "output": result.stdout}
    finally:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


@router.get("/compose/stacks")
def list_compose_stacks():
    """List all Docker Compose stacks (projects)."""
    if shutil.which("docker") is None:
        raise HTTPException(status_code=404, detail="docker not installed")
    
    try:
        output = subprocess.check_output(
            ["docker", "compose", "ls", "--format", "json"],
            text=True
        ).strip()
        
        if not output:
            return []
        
        stacks = json.loads(output)
        return stacks
    except subprocess.CalledProcessError:
        return []
    except json.JSONDecodeError:
        return []


@router.post("/compose/{project_name}/start")
def start_compose_stack(project_name: str):
    """Start all containers in a Docker Compose stack."""
    if shutil.which("docker") is None:
        raise HTTPException(status_code=404, detail="docker not installed")
    
    try:
        # Find containers belonging to this project
        result = subprocess.run(
            ["docker", "compose", "-p", project_name, "start"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to start compose stack")
        
        return {"detail": "Compose stack started", "project": project_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/compose/{project_name}/stop")
def stop_compose_stack(project_name: str):
    """Stop all containers in a Docker Compose stack."""
    if shutil.which("docker") is None:
        raise HTTPException(status_code=404, detail="docker not installed")
    
    try:
        result = subprocess.run(
            ["docker", "compose", "-p", project_name, "stop"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to stop compose stack")
        
        return {"detail": "Compose stack stopped", "project": project_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/compose/{project_name}")
def delete_compose_stack(project_name: str):
    """Delete a Docker Compose stack (down with volumes)."""
    if shutil.which("docker") is None:
        raise HTTPException(status_code=404, detail="docker not installed")
    
    try:
        result = subprocess.run(
            ["docker", "compose", "-p", project_name, "down", "-v"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=400, detail=result.stderr.strip() or "failed to delete compose stack")
        
        return {"detail": "Compose stack deleted", "project": project_name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Compose Manager endpoints
@router.get("/compose-projects")
def list_compose_projects():
    """List all compose projects."""
    return compose_manager.list_projects()


@router.post("/compose-projects")
def create_compose_project(project_info: ComposeProjectInfo):
    """Create a new compose project."""
    result = compose_manager.create_project(project_info.project_name)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@router.post("/compose-projects/{project_name}/services")
def add_service_to_project(project_name: str, service: ComposeServiceCreate):
    """Add a service to a compose project."""
    service_config = service.dict()
    result = compose_manager.add_service_to_project(project_name, service_config)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@router.delete("/compose-projects/{project_name}/services/{service_name}")
def remove_service_from_project(project_name: str, service_name: str):
    """Remove a service from a compose project."""
    result = compose_manager.remove_service_from_project(project_name, service_name)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@router.get("/compose-projects/{project_name}/services/{service_name}")
def get_service_details(project_name: str, service_name: str):
    """Get detailed configuration of a specific service."""
    service = compose_manager.get_service_details(project_name, service_name)
    if service:
        return service
    raise HTTPException(status_code=404, detail="Service not found")


@router.put("/compose-projects/{project_name}/services/{service_name}")
def update_service_in_project(project_name: str, service_name: str, service: ComposeServiceCreate):
    """Update an existing service in a compose project."""
    service_config = service.dict()
    result = compose_manager.update_service_in_project(project_name, service_name, service_config)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@router.get("/compose-projects/{project_name}/compose")
def get_project_compose(project_name: str):
    """Get the compose file content."""
    compose = compose_manager.get_project_compose(project_name)
    if compose:
        return compose
    raise HTTPException(status_code=404, detail="Project not found")


@router.put("/compose-projects/{project_name}/compose")
def update_project_compose(project_name: str, request: Request):
    """Update compose file content."""
    import asyncio
    compose_content = asyncio.run(request.body()).decode('utf-8')
    result = compose_manager.update_project_compose(project_name, compose_content)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@router.post("/compose-projects/{project_name}/start")
def start_compose_project(project_name: str):
    """Start a compose project."""
    result = compose_manager.start_project(project_name)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@router.post("/compose-projects/{project_name}/stop")
def stop_compose_project(project_name: str):
    """Stop a compose project."""
    result = compose_manager.stop_project(project_name)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@router.delete("/compose-projects/{project_name}")
def delete_compose_project_manager(project_name: str, remove_volumes: bool = True):
    """Delete a compose project."""
    result = compose_manager.delete_project(project_name, remove_volumes)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


# App Store endpoints
@router.get("/app-store/apps")
def list_app_store_apps(category: Optional[str] = None, search: Optional[str] = None):
    """List all available apps in the store."""
    if search:
        return app_store.search_apps(search)
    
    apps = app_store.list_apps()
    
    if category:
        apps = [app for app in apps if app.get("category") == category]
    
    return apps


@router.get("/app-store/categories")
def get_app_categories():
    """Get all available app categories."""
    return app_store.get_categories()


@router.get("/app-store/apps/{app_id}")
def get_app_store_app_details(app_id: str):
    """Get detailed information about an app."""
    app = app_store.get_app_details(app_id)
    if app:
        return app
    raise HTTPException(status_code=404, detail="App not found")


@router.get("/app-store/apps/{app_id}/icon")
def get_app_icon(app_id: str):
    """Get the icon image for an app."""
    from fastapi.responses import FileResponse
    import mimetypes
    
    icon_path = app_store.get_app_icon(app_id)
    if icon_path:
        # Detect media type based on file extension
        media_type = mimetypes.guess_type(icon_path)[0] or "image/png"
        return FileResponse(icon_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Icon not found")


class AppInstallRequest(BaseModel):
    custom_name: Optional[str] = None


@router.post("/app-store/apps/{app_id}/install")
def install_app_from_store(app_id: str, request: AppInstallRequest):
    """Install an app from the store."""
    result = app_store.install_app(app_id, request.custom_name)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@router.delete("/app-store/apps/{project_name}/uninstall")
def uninstall_app_from_store(project_name: str):
    """Uninstall an app."""
    result = app_store.uninstall_app(project_name)
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])


@router.get("/volumes")
def list_docker_volumes():
    """List Docker volumes."""
    from containers import get_docker_volumes
    volumes = get_docker_volumes()
    return [v.dict() for v in volumes]


@router.get("/storages")
def list_lxc_storages():
    """List LXC storage pools."""
    from containers import get_lxc_storages
    storages = get_lxc_storages()
    return [s.dict() for s in storages]


@router.post("/volumes")
def create_docker_volume(name: str):
    """Create a new Docker volume."""
    from containers import create_docker_volume
    success = create_docker_volume(name)
    if success:
        return {"message": "Volume created successfully"}
    raise HTTPException(status_code=400, detail="Failed to create volume")


@router.post("/storages")
def create_lxc_storage(name: str, driver: str = "dir", source: str = ""):
    """Create a new LXC storage pool."""
    from containers import create_lxc_storage
    success = create_lxc_storage(name, driver, source)
    if success:
        return {"message": "Storage pool created successfully"}
    raise HTTPException(status_code=400, detail="Failed to create storage pool")