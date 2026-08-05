"""Backup management routes."""

import asyncio
import os
import posixpath
import re
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from lib.backup_db import backup_db
from lib.crontab_manager import crontab_manager
from lib.encryption import get_encryption_manager
from lib.backup_execution import queue_backup_job
from lib.models import (
    BackupServer, BackupServerCreate, BackupServerUpdate,
    BackupJob, BackupJobCreate, BackupJobUpdate, BackupInstance,
    BackupRestoreRequest,
)
from lib.logger import log_backup
from handlers.backup import backup_manager
from handlers.ssh_keys import ssh_key_manager
from lib.jobs import enqueue_job, find_latest_job, has_active_job

router = APIRouter()


def _server_with_credentials(server_id: int) -> Optional[dict]:
    server = backup_db.get_backup_server(server_id, include_secrets=True)
    if not server:
        return None
    encryption = get_encryption_manager()
    if server.get("password_encrypted"):
        server["password"] = encryption.decrypt(server["password_encrypted"])
    if server.get("ssh_key_passphrase_encrypted"):
        server["ssh_key_passphrase"] = encryption.decrypt(
            server["ssh_key_passphrase_encrypted"]
        )
    return server


def _validate_backup_targets(backup_type: str, targets: List[str]) -> None:
    if not targets or any(not str(target).strip() for target in targets):
        raise ValueError("At least one non-empty backup target is required")
    if backup_type == "vm" and any(
        not re.fullmatch(r"vm:[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", target)
        for target in targets
    ):
        raise ValueError("VM backup targets must use vm:NAME")
    if backup_type == "container" and any(
        not re.fullmatch(r"container:[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", target)
        for target in targets
    ):
        raise ValueError("Container backup targets must use container:NAME")
    if backup_type in {"system", "database"} and any(
        not os.path.isabs(target) for target in targets
    ):
        raise ValueError("System and database backup targets must be absolute paths")


# ---------------------------------------------------------------------------
# Backup Servers
# ---------------------------------------------------------------------------

@router.get("/backup/servers", response_model=List[BackupServer])
async def list_backup_servers():
    """List all backup servers from the canonical SQLite store."""
    try:
        return [BackupServer(**server) for server in backup_db.get_backup_servers()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backup servers: {str(e)}")


@router.post("/backup/servers", response_model=BackupServer)
async def create_backup_server(server: BackupServerCreate):
    """Create a backup server and store only encrypted credential material."""
    stored_key_name = None
    try:
        server_data = server.model_dump()
        if any(
            existing["name"] == server_data["name"]
            for existing in backup_db.get_backup_servers()
        ):
            raise HTTPException(status_code=409, detail="Backup server name already exists")
        destination = (
            server_data.get("local_path")
            if server_data["type"] == "local"
            else server_data.get("remote_path")
        )
        if not destination or not os.path.isabs(destination):
            raise HTTPException(
                status_code=422,
                detail="Backup destination paths must be absolute",
            )
        password = server_data.pop("password", None)
        passphrase = server_data.pop("ssh_key_passphrase", None)
        private_key = server_data.pop("ssh_key", None)
        if server_data["type"] == "local":
            password = passphrase = private_key = None
            server_data.update(
                {
                    "host": None,
                    "port": None,
                    "remote_path": None,
                    "auth_type": None,
                    "username": None,
                }
            )
        else:
            server_data["local_path"] = None
            if not server_data.get("host") or not server_data.get("username"):
                raise HTTPException(
                    status_code=422,
                    detail="Remote backup servers require a host and username",
                )
            auth_type = server_data.get("auth_type")
            if auth_type == "password" and not password:
                raise HTTPException(
                    status_code=422,
                    detail="Password authentication requires a password",
                )
            if auth_type == "ssh_key" and not private_key:
                raise HTTPException(
                    status_code=422,
                    detail="SSH key authentication requires a private key",
                )
            if auth_type not in {"password", "ssh_key"}:
                raise HTTPException(
                    status_code=422,
                    detail="Remote backup servers require password or SSH key authentication",
                )
        encryption = get_encryption_manager() if password or passphrase else None
        if password:
            server_data["password_encrypted"] = encryption.encrypt(password)
        if passphrase:
            server_data["ssh_key_passphrase_encrypted"] = encryption.encrypt(passphrase)

        if private_key:
            key_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", f"backup_{server_data['name']}")[:64]
            key_info = ssh_key_manager.store_ssh_key(key_name, private_key, passphrase)
            server_data["ssh_key_path"] = key_info["private_key_path"]
            stored_key_name = key_name

        server_id = backup_db.create_backup_server(server_data)
        stored_key_name = None
        created_server = backup_db.get_backup_server(server_id)
        log_backup(f"Created backup server [{created_server.get('name', server_data.get('name', '?'))}]")
        return BackupServer(**created_server)
    except HTTPException:
        raise
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        if stored_key_name:
            ssh_key_manager.delete_ssh_key(stored_key_name)
        log_backup(f"Failed to create backup server: {e}", error=True)
        raise HTTPException(status_code=500, detail=f"Failed to create backup server: {str(e)}")


@router.get("/backup/servers/{server_id}", response_model=BackupServer)
async def get_backup_server(server_id: int):
    """Get a specific backup server."""
    try:
        server = backup_db.get_backup_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Backup server not found")
        return BackupServer(**server)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backup server: {str(e)}")


@router.put("/backup/servers/{server_id}", response_model=BackupServer)
async def update_backup_server(server_id: int, server: BackupServerUpdate):
    """Update a backup server."""
    try:
        existing_server = backup_db.get_backup_server(server_id, include_secrets=True)
        if not existing_server:
            raise HTTPException(status_code=404, detail="Backup server not found")

        update_data = server.model_dump(exclude_unset=True)
        effective_type = update_data.get("type", existing_server["type"])
        effective_path = update_data.get(
            "local_path" if effective_type == "local" else "remote_path",
            existing_server.get(
                "local_path" if effective_type == "local" else "remote_path"
            ),
        )
        if not effective_path or not os.path.isabs(effective_path):
            raise HTTPException(
                status_code=422,
                detail="Backup destination paths must be absolute",
            )
        if effective_type == "remote":
            update_data["local_path"] = None
            effective_auth = update_data.get(
                "auth_type", existing_server.get("auth_type")
            )
            effective_host = update_data.get("host", existing_server.get("host"))
            effective_username = update_data.get(
                "username", existing_server.get("username")
            )
            if not effective_host or not effective_username:
                raise HTTPException(
                    status_code=422,
                    detail="Remote backup servers require a host and username",
                )
            has_password = (
                bool(update_data.get("password"))
                if "password" in update_data
                else bool(existing_server.get("password_encrypted"))
            )
            has_key = (
                bool(update_data.get("ssh_key"))
                if "ssh_key" in update_data
                else bool(existing_server.get("ssh_key_path"))
            )
            if effective_auth == "password" and not has_password:
                raise HTTPException(
                    status_code=422,
                    detail="Password authentication requires a password",
                )
            if effective_auth == "ssh_key" and not has_key:
                raise HTTPException(
                    status_code=422,
                    detail="SSH key authentication requires a private key",
                )
            if effective_auth not in {"password", "ssh_key"}:
                raise HTTPException(
                    status_code=422,
                    detail="Remote backup servers require password or SSH key authentication",
                )
        else:
            update_data.pop("password", None)
            update_data.pop("ssh_key", None)
            update_data.pop("ssh_key_passphrase", None)
            update_data.update(
                {
                    "host": None,
                    "port": None,
                    "remote_path": None,
                    "auth_type": None,
                    "username": None,
                    "password_encrypted": None,
                    "ssh_key_path": None,
                    "ssh_key_passphrase_encrypted": None,
                }
            )

        key_passphrase = update_data.get("ssh_key_passphrase")
        if "password" in update_data:
            update_data["password_encrypted"] = get_encryption_manager().encrypt(update_data["password"])
            del update_data["password"]

        if "ssh_key_passphrase" in update_data:
            update_data["ssh_key_passphrase_encrypted"] = get_encryption_manager().encrypt(
                update_data["ssh_key_passphrase"]
            )
            del update_data["ssh_key_passphrase"]

        if update_data.get("ssh_key"):
            key_name = re.sub(
                r"[^a-zA-Z0-9_.-]", "_", f"backup_{existing_server['name']}"
            )[:64]
            key_info = ssh_key_manager.store_ssh_key(
                key_name,
                update_data["ssh_key"],
                key_passphrase,
                overwrite=True,
            )
            update_data["ssh_key_path"] = key_info["private_key_path"]
            if key_passphrase is None:
                update_data["ssh_key_passphrase_encrypted"] = None
        if "ssh_key" in update_data:
            del update_data["ssh_key"]

        if not update_data:
            return BackupServer(**existing_server)

        success = backup_db.update_backup_server(server_id, update_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update server")

        updated_server = backup_db.get_backup_server(server_id)
        return BackupServer(**updated_server)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update backup server: {str(e)}")


@router.delete("/backup/servers/{server_id}")
async def delete_backup_server(server_id: int):
    """Delete a backup server."""
    try:
        success = backup_db.delete_backup_server(server_id)
        if not success:
            raise HTTPException(status_code=404, detail="Backup server not found")
        log_backup(f"Deleted backup server [ID:{server_id}]")
        return {"message": "Backup server deleted successfully"}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        log_backup(f"Failed to delete backup server [ID:{server_id}]: {e}", error=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete backup server: {str(e)}")


@router.post("/backup/servers/{server_id}/test")
async def test_backup_server(server_id: int):
    """Test connection to a backup server."""
    try:
        server = _server_with_credentials(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Backup server not found")

        if server["type"] == "local":
            local_path = server.get("local_path") or "/var/lib/upservx/backups"
            if not os.path.exists(local_path):
                os.makedirs(local_path, exist_ok=True)
            success = os.path.isdir(local_path) and os.access(
                local_path, os.W_OK
            )
        else:
            storage = backup_manager._storage_from_server(server)
            storage.remote_path = server.get("remote_path") or "/backups"
            success = await storage.connect()
            if success:
                test_path = posixpath.join(
                    storage.remote_path,
                    f".upservx-write-test-{uuid.uuid4().hex}",
                )
                try:
                    with storage.sftp_client.open(test_path, "w") as handle:
                        handle.write("test")
                    storage.sftp_client.remove(test_path)
                except Exception:
                    success = False
                finally:
                    await storage.disconnect()

        new_status = "connected" if success else "error"
        backup_db.update_backup_server(server_id, {"status": new_status})
        server_name = server.get("name", f"ID:{server_id}")
        if success:
            log_backup(f"Successfully connected to Backup Server [{server_name}]")
        else:
            log_backup(f"Connection test failed for Backup Server [{server_name}]", error=True)
        return {"success": success, "status": new_status}
    except HTTPException:
        raise
    except Exception as e:
        try:
            backup_db.update_backup_server(server_id, {"status": "error"})
        except Exception:
            pass
        log_backup(f"Error testing Backup Server [ID:{server_id}]: {e}", error=True)
        raise HTTPException(status_code=500, detail=f"Failed to test backup server: {str(e)}")


@router.get("/backup/servers/{server_id}/info")
async def get_backup_server_info(server_id: int):
    """Return live capacity information for a configured destination."""
    server = _server_with_credentials(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Backup server not found")
    if server["type"] == "local":
        path = server.get("local_path") or "/var/lib/upservx/backups"
        os.makedirs(path, exist_ok=True)
        stat = os.statvfs(path)
        total = stat.f_frsize * stat.f_blocks
        available = stat.f_frsize * stat.f_available
        storage_info = {
            "type": "local",
            "total_gb": round(total / (1024 ** 3), 2),
            "used_gb": round((total - available) / (1024 ** 3), 2),
            "available_gb": round(available / (1024 ** 3), 2),
        }
        backup_db.update_backup_server(
            server_id,
            {
                "status": "connected",
                "capacity_gb": storage_info["total_gb"],
                "used_gb": storage_info["used_gb"],
                "last_sync": datetime.now().isoformat(),
            },
        )
        return {
            "server_id": server_id,
            "name": server["name"],
            "type": server["type"],
            "status": "connected",
            "storage_info": storage_info,
        }
    storage = backup_manager._storage_from_server(server)
    storage.remote_path = server.get("remote_path") or "/backups"
    if not await storage.connect():
        backup_db.update_backup_server(server_id, {"status": "error"})
        raise HTTPException(status_code=502, detail="Could not connect to backup server")
    try:
        storage_info = await storage.get_storage_info()
    finally:
        await storage.disconnect()
    if not storage_info:
        backup_db.update_backup_server(server_id, {"status": "error"})
        raise HTTPException(status_code=502, detail="Could not read backup storage capacity")
    backup_db.update_backup_server(
        server_id,
        {
            "status": "connected",
            "capacity_gb": storage_info.get("total_gb"),
            "used_gb": storage_info.get("used_gb"),
            "last_sync": datetime.now().isoformat(),
        },
    )
    return {
        "server_id": server_id,
        "name": server["name"],
        "type": server["type"],
        "status": "connected",
        "storage_info": storage_info,
    }


# ---------------------------------------------------------------------------
# Backup Jobs
# ---------------------------------------------------------------------------

@router.get("/backup/jobs", response_model=List[BackupJob])
async def list_backup_jobs():
    """List all backup jobs."""
    try:
        jobs = backup_db.get_backup_jobs()
        return [BackupJob(**job) for job in jobs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backup jobs: {str(e)}")


@router.post("/backup/jobs", response_model=BackupJob)
async def create_backup_job(job: BackupJobCreate):
    """Create a new backup job."""
    try:
        job_data = job.model_dump()
        if not backup_db.get_backup_server(job_data["server_id"]):
            raise HTTPException(status_code=400, detail="Backup server not found")
        _validate_backup_targets(job_data["backup_type"], job_data["targets"])
        crontab_manager._validate_schedule(job_data["schedule"])
        job_id = backup_db.create_backup_job(job_data)

        created_job = backup_db.get_backup_job(job_id)
        if not created_job:
            raise HTTPException(status_code=500, detail="Failed to retrieve created job")

        success = crontab_manager.add_backup_job(
            job_id=job_id,
            schedule=created_job["schedule"],
            job_name=created_job["name"],
        )
        if not success:
            backup_db.delete_backup_job(job_id)
            raise HTTPException(status_code=500, detail="Failed to install cron schedule")

        log_backup(
            f"Created backup job [{created_job['name']}] (ID:{job_id}, schedule: {created_job['schedule']})"
        )
        return BackupJob(**created_job)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        log_backup(f"Failed to create backup job: {e}", error=True)
        raise HTTPException(status_code=500, detail=f"Failed to create backup job: {str(e)}")


@router.get("/backup/jobs/{job_id}", response_model=BackupJob)
async def get_backup_job(job_id: int):
    """Get a specific backup job."""
    try:
        job = backup_db.get_backup_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Backup job not found")
        return BackupJob(**job)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backup job: {str(e)}")


@router.put("/backup/jobs/{job_id}", response_model=BackupJob)
async def update_backup_job(job_id: int, job: BackupJobUpdate):
    """Update a backup job."""
    try:
        existing_job = backup_db.get_backup_job(job_id)
        if not existing_job:
            raise HTTPException(status_code=404, detail="Backup job not found")
        update_data = job.model_dump(exclude_unset=True)
        if not update_data:
            return BackupJob(**existing_job)
        server_id = update_data.get("server_id")
        if server_id is not None and not backup_db.get_backup_server(server_id):
            raise HTTPException(status_code=400, detail="Backup server not found")
        if "schedule" in update_data:
            crontab_manager._validate_schedule(update_data["schedule"])
        _validate_backup_targets(
            update_data.get("backup_type", existing_job["backup_type"]),
            update_data.get("targets", existing_job["targets"]),
        )
        success = backup_db.update_backup_job(job_id, update_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update job")

        updated_job = backup_db.get_backup_job(job_id)
        if updated_job["status"] == "active":
            cron_success = crontab_manager.add_backup_job(
                job_id, updated_job["schedule"], updated_job["name"]
            )
        else:
            cron_success = crontab_manager.remove_backup_job(job_id)
        if not cron_success:
            rollback = {
                key: existing_job[key]
                for key in (
                    "name", "backup_type", "targets", "schedule", "server_id",
                    "status", "last_run", "next_run", "last_size",
                    "retention_days", "compression",
                )
            }
            backup_db.update_backup_job(job_id, rollback)
            if existing_job["status"] == "active":
                crontab_manager.add_backup_job(
                    job_id, existing_job["schedule"], existing_job["name"]
                )
            else:
                crontab_manager.remove_backup_job(job_id)
            raise HTTPException(
                status_code=500,
                detail="Cron schedule update failed; job changes were rolled back",
            )
        return BackupJob(**updated_job)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update backup job: {str(e)}")


@router.delete("/backup/jobs/{job_id}")
async def delete_backup_job(job_id: int):
    """Delete a backup job."""
    try:
        existing_job = backup_db.get_backup_job(job_id)
        if not existing_job:
            raise HTTPException(status_code=404, detail="Backup job not found")
        if has_active_job("backup_job", job_id):
            raise HTTPException(status_code=409, detail="Backup job is currently running")
        crontab_success = crontab_manager.remove_backup_job(job_id)
        if not crontab_success:
            raise HTTPException(status_code=500, detail="Could not remove cron schedule")

        instances = backup_db.get_backup_instances(job_id=job_id)
        needs_storage = any(instance.get("backup_path") for instance in instances)
        server = (
            _server_with_credentials(existing_job["server_id"])
            if needs_storage
            else backup_db.get_backup_server(existing_job["server_id"])
        )
        if not server:
            if existing_job["status"] == "active":
                crontab_manager.add_backup_job(
                    job_id, existing_job["schedule"], existing_job["name"]
                )
            raise HTTPException(status_code=409, detail="Backup server is unavailable")
        for instance in instances:
            deleted = await asyncio.to_thread(
                backup_manager.delete_instance_archive, instance, server
            )
            if not deleted:
                if existing_job["status"] == "active":
                    crontab_manager.add_backup_job(
                        job_id, existing_job["schedule"], existing_job["name"]
                    )
                raise HTTPException(
                    status_code=502,
                    detail=f"Could not delete archive for backup instance {instance['id']}",
                )
            backup_db.delete_backup_instance(int(instance["id"]))
        success = backup_db.delete_backup_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Backup job not found")

        log_backup(f"Deleted backup job [ID:{job_id}]")
        return {"message": "Backup job deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        log_backup(f"Failed to delete backup job [ID:{job_id}]: {e}", error=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete backup job: {str(e)}")


@router.post("/backup/jobs/{job_id}/execute", status_code=202)
async def execute_backup_job(job_id: int):
    """Queue a backup for execution by the persistent worker."""
    try:
        persistent_job = queue_backup_job(job_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Backup job not found")
    return {
        "message": "Backup queued",
        "job_id": job_id,
        "persistent_job": persistent_job,
    }


@router.post("/backup/jobs/{job_id}/trigger", status_code=202)
async def trigger_backup_job(job_id: int):
    """Compatibility alias for durable backup execution."""
    return await execute_backup_job(job_id)


@router.get("/backup/jobs/{job_id}/progress")
async def get_backup_job_progress(job_id: int):
    """Get latest progress for a backup job."""
    job = find_latest_job("backup_job", job_id)
    if not job:
        return {
            "job_id": job_id,
            "status": "idle",
            "progress": 0,
            "message": "No active backup run",
            "updated_at": None,
        }
    return {
        "job_id": job_id,
        "persistent_job_id": job["id"],
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "error": job["error"],
        "result": job["result"],
        "updated_at": job["updated_at"],
    }


# ---------------------------------------------------------------------------
# Backup Instances
# ---------------------------------------------------------------------------

@router.get("/backup/instances", response_model=List[BackupInstance])
async def list_backup_instances(
    job_id: Optional[int] = None,
    server_id: Optional[int] = None,
    limit: Optional[int] = 100,
):
    """List backup instances with optional filtering."""
    try:
        instances = backup_db.get_backup_instances(job_id=job_id, server_id=server_id, limit=limit)
        return [BackupInstance(**instance) for instance in instances]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backup instances: {str(e)}")


@router.get("/backup/instances/{instance_id}", response_model=BackupInstance)
async def get_backup_instance(instance_id: int):
    """Get a specific backup instance."""
    try:
        instance = backup_db.get_backup_instance(instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Backup instance not found")
        return BackupInstance(**instance)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backup instance: {str(e)}")


@router.delete("/backup/instances/{instance_id}")
async def delete_backup_instance(instance_id: int):
    """Delete an archive first and its metadata only after storage confirms."""
    try:
        instance = backup_db.get_backup_instance(instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Backup instance not found")
        if has_active_job("backup_instance", instance_id):
            raise HTTPException(
                status_code=409,
                detail="A restore or verification is using this backup archive",
            )
        if not instance.get("backup_path"):
            backup_db.delete_backup_instance(instance_id)
            return {"message": "Backup instance deleted successfully"}
        server = _server_with_credentials(instance["server_id"])
        if not server:
            raise HTTPException(status_code=409, detail="Backup server is unavailable")
        deleted = await asyncio.to_thread(
            backup_manager.delete_instance_archive, instance, server
        )
        if not deleted:
            raise HTTPException(status_code=502, detail="Could not delete backup archive")
        success = backup_db.delete_backup_instance(instance_id)
        if not success:
            raise HTTPException(status_code=404, detail="Backup instance not found")
        return {"message": "Backup instance deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete backup instance: {str(e)}")


@router.post("/backup/instances/{instance_id}/restore", status_code=202)
async def restore_backup_instance(instance_id: int, request: BackupRestoreRequest):
    """Queue a verified, non-overwriting restore through the persistent worker."""
    instance = backup_db.get_backup_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Backup instance not found")
    if instance["status"] != "completed" or not instance.get("backup_path"):
        raise HTTPException(status_code=409, detail="Backup archive is not restorable")
    persistent_job = enqueue_job(
        "backup_restore",
        {
            "instance_id": instance_id,
            "restore_path": request.restore_path,
        },
        idempotency_key=f"backup-restore:{instance_id}:{request.restore_path}",
        resource_type="backup_instance",
        resource_id=instance_id,
    )
    return {"message": "Restore queued", "persistent_job": persistent_job}


@router.post("/backup/instances/{instance_id}/verify", status_code=202)
async def verify_backup_instance(instance_id: int):
    """Queue checksum validation plus an isolated test restore."""
    instance = backup_db.get_backup_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Backup instance not found")
    if instance["status"] != "completed" or not instance.get("backup_path"):
        raise HTTPException(status_code=409, detail="Backup archive is not verifiable")
    persistent_job = enqueue_job(
        "backup_verify",
        {"instance_id": instance_id},
        idempotency_key=f"backup-verify:{instance_id}",
        resource_type="backup_instance",
        resource_id=instance_id,
    )
    return {"message": "Verification queued", "persistent_job": persistent_job}


# ---------------------------------------------------------------------------
# Cron jobs
# ---------------------------------------------------------------------------

@router.get("/backup/cron-jobs")
async def get_backup_cron_jobs():
    """Get all backup jobs currently scheduled in crontab."""
    try:
        return crontab_manager.list_backup_jobs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list cron jobs: {str(e)}")
