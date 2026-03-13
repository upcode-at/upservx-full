"""Backup management routes."""

import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from lib.backup_db import backup_db
from lib.config_manager import get_config_manager
from lib.crontab_manager import crontab_manager
from lib.models import (
    BackupServer, BackupServerCreate, BackupServerUpdate,
    BackupJob, BackupJobCreate, BackupJobUpdate, BackupInstance,
)
from lib.logger import log_backup
from handlers.backup import backup_manager, BackupAuthConfig
from handlers.ssh_keys import ssh_key_manager
from handlers.notifications import notify

router = APIRouter()


# ---------------------------------------------------------------------------
# Backup Servers
# ---------------------------------------------------------------------------

@router.get("/backup/servers", response_model=List[BackupServer])
async def list_backup_servers():
    """List all backup servers from /etc/upservx configuration."""
    try:
        config = get_config_manager()
        servers = config.get_backup_servers()
        return [BackupServer(**server) for server in servers]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backup servers: {str(e)}")


@router.post("/backup/servers", response_model=BackupServer)
async def create_backup_server(server: BackupServerCreate):
    """Create a new backup server in /etc/upservx configuration."""
    try:
        config = get_config_manager()
        server_data = server.model_dump()

        if server_data.get("ssh_key"):
            key_name = f"backup_{server_data['name'].replace(' ', '_').lower()}"
            key_path = config.save_ssh_key(key_name, server_data["ssh_key"])
            server_data["ssh_key_path"] = key_path
            del server_data["ssh_key"]

        created_server = config.add_backup_server(server_data)
        log_backup(f"Created backup server [{created_server.get('name', server_data.get('name', '?'))}]")
        return BackupServer(**created_server)
    except Exception as e:
        log_backup(f"Failed to create backup server: {e}", error=True)
        raise HTTPException(status_code=500, detail=f"Failed to create backup server: {str(e)}")


@router.get("/backup/servers/{server_id}", response_model=BackupServer)
async def get_backup_server(server_id: int):
    """Get a specific backup server."""
    try:
        config = get_config_manager()
        server = config.get_backup_server(server_id)
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
        existing_server = backup_db.get_backup_server(server_id)
        if not existing_server:
            raise HTTPException(status_code=404, detail="Backup server not found")

        update_data = server.model_dump(exclude_unset=True)

        if "password" in update_data:
            update_data["password_encrypted"] = backup_manager.encrypt_sensitive_data(update_data["password"])
            del update_data["password"]

        if "ssh_key_passphrase" in update_data:
            update_data["ssh_key_passphrase_encrypted"] = backup_manager.encrypt_sensitive_data(
                update_data["ssh_key_passphrase"]
            )
            del update_data["ssh_key_passphrase"]

        if "ssh_key" in update_data:
            ssh_key_path = ssh_key_manager.store_ssh_key(
                f"backup_server_{existing_server['name']}",
                update_data["ssh_key"],
                update_data.get("ssh_key_passphrase_encrypted"),
            )
            update_data["ssh_key_path"] = ssh_key_path
            del update_data["ssh_key"]

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
        config = get_config_manager()
        success = config.delete_backup_server(server_id)
        if not success:
            raise HTTPException(status_code=404, detail="Backup server not found")
        log_backup(f"Deleted backup server [ID:{server_id}]")
        return {"message": "Backup server deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        log_backup(f"Failed to delete backup server [ID:{server_id}]: {e}", error=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete backup server: {str(e)}")


@router.post("/backup/servers/{server_id}/test")
async def test_backup_server(server_id: int):
    """Test connection to a backup server."""
    try:
        server = backup_db.get_backup_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Backup server not found")

        if server["type"] == "local":
            import os
            if not os.path.exists(server["local_path"]):
                os.makedirs(server["local_path"], exist_ok=True)
            success = os.path.isdir(server["local_path"])
        else:
            auth_config = BackupAuthConfig(
                auth_type=server["auth_type"],
                username=server["username"],
                password=backup_manager.decrypt_sensitive_data(server.get("password_encrypted"))
                if server.get("password_encrypted")
                else None,
                ssh_key_path=server.get("ssh_key_path"),
                ssh_key_passphrase=backup_manager.decrypt_sensitive_data(
                    server.get("ssh_key_passphrase_encrypted")
                )
                if server.get("ssh_key_passphrase_encrypted")
                else None,
            )
            success = backup_manager.test_connection(server["host"], server["port"], auth_config)

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
        log_backup(f"Error testing Backup Server [ID:{server_id}]: {e}", error=True)
        raise HTTPException(status_code=500, detail=f"Failed to test backup server: {str(e)}")


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
            logging.warning(f"Failed to add backup job {job_id} to crontab")

        log_backup(
            f"Created backup job [{created_job['name']}] (ID:{job_id}, schedule: {created_job['schedule']})"
        )
        return BackupJob(**created_job)
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
        success = backup_db.update_backup_job(job_id, update_data)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update job")

        updated_job = backup_db.get_backup_job(job_id)
        return BackupJob(**updated_job)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update backup job: {str(e)}")


@router.delete("/backup/jobs/{job_id}")
async def delete_backup_job(job_id: int):
    """Delete a backup job."""
    try:
        crontab_success = crontab_manager.remove_backup_job(job_id)
        if not crontab_success:
            logging.warning(f"Failed to remove backup job {job_id} from crontab")

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


@router.post("/backup/jobs/{job_id}/execute")
async def execute_backup_job(job_id: int):
    """Execute a backup job immediately."""
    try:
        job = backup_db.get_backup_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Backup job not found")

        config = get_config_manager()
        server = config.get_backup_server(job["server_id"])
        if not server:
            raise HTTPException(status_code=404, detail="Backup server not found")

        instance_data = {
            "job_id": job_id,
            "server_id": job["server_id"],
            "backup_name": f"{job['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "backup_path": "",
            "backup_type": job["backup_type"],
            "targets": json.dumps(job["targets"]) if isinstance(job["targets"], list) else job["targets"],
            "started": datetime.now().isoformat(),
        }

        instance_id = backup_db.create_backup_instance(instance_data)

        try:
            result = backup_manager.execute_backup(job, server)

            if result.get("success", False):
                backup_db.update_backup_instance(
                    instance_id,
                    {
                        "status": "completed",
                        "backup_size": result.get("size", 0),
                        "backup_path": result.get("backup_path", ""),
                        "completed": datetime.now().isoformat(),
                        "error_message": None,
                    },
                )
                log_backup(
                    f"Backup job [{job['name']}] completed successfully (size: {result.get('size', 0)} bytes)"
                )
                size_mb = round(result.get("size", 0) / 1024 / 1024, 2)
                notify(
                    "backup_success",
                    f"Backup job '{job['name']}' completed | Size: {size_mb} MB | Path: {result.get('backup_path', 'n/a')}",
                )
                return {
                    "message": "Backup job executed successfully",
                    "instance_id": instance_id,
                    "backup_path": result.get("backup_path"),
                    "size": result.get("size", 0),
                }
            else:
                backup_db.update_backup_instance(
                    instance_id,
                    {
                        "status": "failed",
                        "completed": datetime.now().isoformat(),
                        "error_message": result.get("error", "Backup execution failed"),
                    },
                )
                log_backup(f"Backup job [{job['name']}] failed: {result.get('error')}", error=True)
                notify(
                    "backup_failure",
                    f"Backup job '{job['name']}' failed: {result.get('error', 'Unknown error')}",
                )
                raise HTTPException(status_code=500, detail=f"Backup failed: {result.get('error')}")

        except HTTPException:
            raise
        except Exception as backup_error:
            backup_db.update_backup_instance(
                instance_id,
                {
                    "status": "failed",
                    "completed": datetime.now().isoformat(),
                    "error_message": str(backup_error),
                },
            )
            raise HTTPException(status_code=500, detail=f"Backup execution error: {str(backup_error)}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute backup job: {str(e)}")


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
    """Delete a backup instance."""
    try:
        success = backup_db.delete_backup_instance(instance_id)
        if not success:
            raise HTTPException(status_code=404, detail="Backup instance not found")
        return {"message": "Backup instance deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete backup instance: {str(e)}")


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
