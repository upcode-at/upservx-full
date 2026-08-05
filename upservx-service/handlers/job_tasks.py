"""Long-running task implementations executed only by ``job_runner.py``."""

from __future__ import annotations

import asyncio
import os
import subprocess
from datetime import datetime
from typing import Any, Callable

from lib.jobs import JobContext


TaskHandler = Callable[[dict[str, Any], JobContext], Any]


def _backup(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    from handlers.backup import backup_manager
    from handlers.notifications import notify
    from lib.backup_db import backup_db
    from lib.config_manager import get_config_manager
    from lib.logger import log_backup

    backup_job_id = int(payload["backup_job_id"])
    backup_job = backup_db.get_backup_job(backup_job_id)
    if not backup_job:
        raise RuntimeError("Backup job not found")
    server = get_config_manager().get_backup_server(
        backup_job["server_id"],
        include_secret=True,
    )
    if not server:
        raise RuntimeError("Backup server not found")

    checkpoint = context.checkpoint or {}
    instance_id = checkpoint.get("instance_id")
    existing_instance = (
        backup_db.get_backup_instance(int(instance_id)) if instance_id else None
    )
    if existing_instance and existing_instance.get("status") == "completed":
        return {
            "message": "Backup completed",
            "backup_job_id": backup_job_id,
            "instance_id": int(instance_id),
            "backup_path": existing_instance.get("backup_path"),
            "size": int(existing_instance.get("backup_size", 0) or 0),
            "resumed": True,
        }
    if existing_instance:
        instance_id = int(instance_id)
        backup_db.update_backup_instance(
            instance_id,
            {"status": "in_progress", "error_message": None, "completed": None},
        )
    else:
        instance_id = backup_db.create_backup_instance(
            {
                "job_id": backup_job_id,
                "server_id": backup_job["server_id"],
                "backup_name": (
                    f"{backup_job['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                ),
                "backup_path": "",
                "backup_size": 0,
                "status": "in_progress",
                "backup_type": backup_job["backup_type"],
                "targets": backup_job["targets"],
                "error_message": None,
                "started": datetime.now().isoformat(),
                "completed": None,
            }
        )

    context.progress(
        2,
        "Preparing backup",
        checkpoint={"stage": "preparing", "instance_id": instance_id},
        save_checkpoint=True,
    )
    notify(
        "backup_started",
        f"Backup job '{backup_job['name']}' started | "
        f"Type: {backup_job.get('backup_type', 'unknown')} | "
        f"Server: {server.get('name', server.get('host', 'unknown'))}",
    )

    def progress(value: int, message: str) -> None:
        context.progress(
            value,
            message,
            checkpoint={
                "stage": "executing",
                "instance_id": instance_id,
                "progress": value,
            },
            save_checkpoint=True,
        )

    try:
        result = backup_manager.execute_backup(
            backup_job,
            server,
            progress_callback=progress,
        )
        if not result.get("success", False):
            raise RuntimeError(result.get("error", "Backup execution failed"))
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
        size = int(result.get("size", 0) or 0)
        log_backup(
            f"Backup job [{backup_job['name']}] completed successfully "
            f"(size: {size} bytes)"
        )
        notify(
            "backup_success",
            f"Backup job '{backup_job['name']}' completed | "
            f"Size: {round(size / 1024 / 1024, 2)} MB | "
            f"Path: {result.get('backup_path', 'n/a')}",
        )
        return {
            "message": "Backup completed",
            "backup_job_id": backup_job_id,
            "instance_id": instance_id,
            "backup_path": result.get("backup_path"),
            "size": size,
        }
    except Exception as error:
        backup_db.update_backup_instance(
            instance_id,
            {
                "status": "failed",
                "completed": datetime.now().isoformat(),
                "error_message": str(error),
            },
        )
        log_backup(f"Backup job [{backup_job['name']}] failed: {error}", error=True)
        notify(
            "backup_failure",
            f"Backup job '{backup_job['name']}' failed: {error}",
        )
        raise


def _replication(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    from api.cluster import execute_replication, read_replications

    replication_id = str(payload["replication_id"])
    if (context.checkpoint or {}).get("stage") == "completed":
        return {
            "message": "Replication completed",
            "replication_id": replication_id,
            "resumed": True,
        }
    replication = next(
        (item for item in read_replications() if item.get("id") == replication_id),
        None,
    )
    if not replication:
        raise RuntimeError("Replication rule not found")

    def progress(value: int, message: str, status: str = "running") -> None:
        context.progress(
            value,
            message,
            checkpoint={"stage": status, "progress": value},
            save_checkpoint=True,
        )

    context.progress(2, "Preparing replication")
    success = asyncio.run(execute_replication(replication, progress_callback=progress))
    if not success:
        raise RuntimeError("Replication failed")
    return {"message": "Replication completed", "replication_id": replication_id}


def _vm_export(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    from handlers.vms import export_vm_ova
    from lib.logger import log_vm

    name = str(payload["name"])
    export_format = str(payload.get("format", "ova")).lower()
    resumed_path = (context.checkpoint or {}).get("path")
    if resumed_path and os.path.isfile(resumed_path):
        return {
            "message": "VM export completed",
            "name": name,
            "filename": os.path.basename(resumed_path),
            "path": resumed_path,
            "resumed": True,
        }
    context.progress(
        5,
        "Preparing VM export",
        checkpoint={"stage": "preparing"},
        save_checkpoint=True,
    )
    path = export_vm_ova(name, export_format=export_format)
    context.progress(
        95,
        "Finalizing VM export",
        checkpoint={"stage": "finalizing", "path": path},
        save_checkpoint=True,
    )
    log_vm(f"Exported VM [{name}] as {export_format.upper()} -> [{path}]")
    return {
        "message": "VM export completed",
        "name": name,
        "filename": os.path.basename(path),
        "path": path,
    }


def _cluster_export(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    from api.cluster import _export_resource_now

    resource_type = str(payload["resource_type"])
    resource_name = str(payload["resource_name"])
    checkpoint = context.checkpoint or {}
    resumed_path = checkpoint.get("export_path")
    if resumed_path and os.path.isfile(resumed_path):
        return {
            "export_path": resumed_path,
            "export_id": checkpoint.get("export_id"),
            "resumed": True,
        }
    context.progress(
        5,
        "Preparing cluster export",
        checkpoint={"stage": "preparing"},
        save_checkpoint=True,
    )
    result = asyncio.run(_export_resource_now(resource_type, resource_name))
    context.progress(
        95,
        "Finalizing cluster export",
        checkpoint={"stage": "finalizing", **result},
        save_checkpoint=True,
    )
    return result


def _cve_scan(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    from handlers.security import scan_cves

    context.progress(5, "Scanning installed packages")
    result = scan_cves(limit=int(payload.get("limit", 300)))
    context.check_cancelled()
    return result


def _container_cve_scan(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    from handlers.security import scan_container_cves

    context.progress(5, "Scanning container packages")
    result = scan_container_cves(
        container_limit=int(payload.get("container_limit", 30)),
        package_limit=int(payload.get("package_limit", 200)),
    )
    context.check_cancelled()
    return result


def _package_scan(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    from handlers.security import get_upgradeable_packages

    context.progress(5, "Refreshing package metadata")
    result = get_upgradeable_packages()
    context.check_cancelled()
    return result


def _package_upgrade(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    from handlers.security import upgrade_package

    package_name = payload.get("package_name")
    checkpoint = context.checkpoint or {}
    if checkpoint.get("stage") == "completed" and isinstance(
        checkpoint.get("result"),
        dict,
    ):
        return checkpoint["result"]
    context.progress(
        5,
        f"Upgrading {package_name}" if package_name else "Upgrading packages",
        checkpoint={"stage": "upgrading", "package_name": package_name},
        save_checkpoint=True,
    )
    result = upgrade_package(package_name)
    context.check_cancelled()
    if not result.get("success"):
        raise RuntimeError(result.get("error", "Package upgrade failed"))
    context.progress(
        95,
        "Package upgrade completed",
        checkpoint={"stage": "completed", "result": result},
        save_checkpoint=True,
    )
    return result


def _system_update(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    checkpoint = context.checkpoint or {}
    if checkpoint.get("stage") == "completed" and isinstance(
        checkpoint.get("result"),
        dict,
    ):
        return checkpoint["result"]
    update_script = str(payload.get("script", "/opt/upservx/update.sh"))
    if update_script != "/opt/upservx/update.sh" or not os.path.isfile(update_script):
        raise RuntimeError("update.sh not found")
    context.progress(
        5,
        "Running system update",
        checkpoint={"stage": "updating"},
        save_checkpoint=True,
    )
    result = subprocess.run(
        ["sudo", "bash", update_script],
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
    )
    context.check_cancelled()
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Update failed")[-8000:]
        raise RuntimeError(detail)
    completed_result = {
        "message": "System update completed",
        "exit_code": result.returncode,
        "stdout": result.stdout[-20_000:],
        "stderr": result.stderr[-20_000:],
    }
    context.progress(
        95,
        "System update completed",
        checkpoint={"stage": "completed", "result": completed_result},
        save_checkpoint=True,
    )
    return completed_result


TASK_HANDLERS: dict[str, TaskHandler] = {
    "backup": _backup,
    "replication": _replication,
    "vm_export": _vm_export,
    "cluster_export": _cluster_export,
    "cve_scan": _cve_scan,
    "container_cve_scan": _container_cve_scan,
    "package_scan": _package_scan,
    "package_upgrade": _package_upgrade,
    "system_update": _system_update,
}


def run_task(kind: str, payload: dict[str, Any], context: JobContext) -> Any:
    try:
        handler = TASK_HANDLERS[kind]
    except KeyError as error:
        raise RuntimeError(f"No handler registered for job kind {kind}") from error
    return handler(payload, context)
