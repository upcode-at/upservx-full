"""Long-running task implementations executed only by ``job_runner.py``."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from lib.jobs import JobCancelledError, JobContext
from lib.privileged import run_privileged


TaskHandler = Callable[[dict[str, Any], JobContext], Any]


def _backup(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    from handlers.backup import backup_manager
    from handlers.notifications import notify
    from lib.backup_db import backup_db
    from lib.encryption import get_encryption_manager
    from lib.logger import log_backup

    backup_job_id = int(payload["backup_job_id"])
    backup_job = backup_db.get_backup_job(backup_job_id)
    if not backup_job:
        raise RuntimeError("Backup job not found")
    server = backup_db.get_backup_server(backup_job["server_id"], include_secrets=True)
    if not server:
        raise RuntimeError("Backup server not found")
    encryption = get_encryption_manager()
    if server.get("password_encrypted"):
        server["password"] = encryption.decrypt(server["password_encrypted"])
    if server.get("ssh_key_passphrase_encrypted"):
        server["ssh_key_passphrase"] = encryption.decrypt(
            server["ssh_key_passphrase_encrypted"]
        )

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
        if existing_instance.get("backup_path"):
            if not backup_manager.delete_instance_archive(existing_instance, server):
                raise RuntimeError("Could not remove the archive from a failed backup attempt")
        backup_db.update_backup_instance(
            instance_id,
            {
                "status": "in_progress",
                "backup_path": "",
                "backup_size": 0,
                "error_message": None,
                "integrity_status": "pending",
                "completed": None,
            },
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
                "integrity_status": "pending",
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

    result: dict[str, Any] = {}
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
                "checksum_sha256": result.get("checksum_sha256"),
                "integrity_status": result.get("integrity_status", "verified"),
                "verified_at": datetime.now().isoformat(),
                "last_test_restore": (
                    datetime.now().isoformat() if result.get("test_restore") else None
                ),
            },
        )
        backup_db.update_backup_job(
            backup_job_id,
            {
                "last_run": datetime.now().isoformat(),
                "last_size": result.get("size", 0),
            },
        )

        # Retention is archive-aware: metadata is removed only after the local
        # or remote object has been deleted successfully.
        retention_failures = []
        for expired in backup_db.get_expired_instances(
            backup_job_id, backup_job.get("retention_days", 30)
        ):
            if int(expired["id"]) == int(instance_id):
                continue
            try:
                if backup_manager.delete_instance_archive(expired, server):
                    backup_db.delete_backup_instance(int(expired["id"]))
                else:
                    retention_failures.append(int(expired["id"]))
            except Exception:
                retention_failures.append(int(expired["id"]))
        if retention_failures:
            log_backup(
                "Retention could not remove backup instances "
                + ", ".join(str(value) for value in retention_failures),
                error=True,
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
            "retention_failures": retention_failures,
        }
    except Exception as error:
        archive_path = result.get("backup_path")
        remaining_archive_path = ""
        if archive_path:
            try:
                if not backup_manager.delete_instance_archive(
                    {"backup_path": archive_path}, server
                ):
                    remaining_archive_path = archive_path
                    log_backup(
                        f"Could not clean failed backup archive [{archive_path}]",
                        error=True,
                    )
            except Exception:
                remaining_archive_path = archive_path
                log_backup(
                    f"Could not clean failed backup archive [{archive_path}]",
                    error=True,
                )
        backup_db.update_backup_job(
            backup_job_id,
            {"last_run": datetime.now().isoformat()},
        )
        backup_db.update_backup_instance(
            instance_id,
            {
                "status": "failed",
                "backup_path": remaining_archive_path,
                "backup_size": (
                    result.get("size", 0) if remaining_archive_path else 0
                ),
                "integrity_status": "error",
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


def _backup_restore(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    from handlers.backup import backup_manager
    from lib.backup_db import backup_db
    from lib.encryption import get_encryption_manager

    instance_id = int(payload["instance_id"])
    instance = backup_db.get_backup_instance(instance_id)
    if not instance:
        raise RuntimeError("Backup instance not found")
    server = backup_db.get_backup_server(instance["server_id"], include_secrets=True)
    if not server:
        raise RuntimeError("Backup server not found")
    encryption = get_encryption_manager()
    if server.get("password_encrypted"):
        server["password"] = encryption.decrypt(server["password_encrypted"])
    if server.get("ssh_key_passphrase_encrypted"):
        server["ssh_key_passphrase"] = encryption.decrypt(
            server["ssh_key_passphrase_encrypted"]
        )
    context.progress(10, "Verifying backup archive")
    result = backup_manager.restore_instance(
        instance,
        server,
        str(payload["restore_path"]),
        overwrite=False,
    )
    backup_db.update_backup_instance(
        instance_id,
        {
            "checksum_sha256": result["checksum_sha256"],
            "integrity_status": result["integrity_status"],
            "verified_at": datetime.now().isoformat(),
        },
    )
    context.progress(100, "Backup restored")
    return result


def _backup_verify(payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
    from handlers.backup import backup_manager
    from lib.backup_db import backup_db
    from lib.encryption import get_encryption_manager

    instance_id = int(payload["instance_id"])
    instance = backup_db.get_backup_instance(instance_id)
    if not instance:
        raise RuntimeError("Backup instance not found")
    server = backup_db.get_backup_server(instance["server_id"], include_secrets=True)
    if not server:
        raise RuntimeError("Backup server not found")
    encryption = get_encryption_manager()
    if server.get("password_encrypted"):
        server["password"] = encryption.decrypt(server["password_encrypted"])
    if server.get("ssh_key_passphrase_encrypted"):
        server["ssh_key_passphrase"] = encryption.decrypt(
            server["ssh_key_passphrase_encrypted"]
        )
    context.progress(10, "Verifying backup archive")
    try:
        result = backup_manager.verify_instance(instance, server, test_restore=True)
    except Exception:
        backup_db.update_backup_instance(
            instance_id,
            {
                "integrity_status": "error",
                "verified_at": datetime.now().isoformat(),
            },
        )
        raise
    now = datetime.now().isoformat()
    backup_db.update_backup_instance(
        instance_id,
        {
            "checksum_sha256": result["checksum_sha256"],
            "integrity_status": result["integrity_status"],
            "verified_at": now,
            "last_test_restore": now,
        },
    )
    context.progress(100, "Backup verified and test-restored")
    return {"instance_id": instance_id, **result, "test_restore": True}


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
    version = str(payload.get("version", ""))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", version):
        raise RuntimeError("invalid update version")
    state_root = Path(
        os.getenv("UPCODE_HARBOR_UPDATE_STATE_ROOT", "/var/lib/upcode-harbor/update-state")
    )
    state_path = state_root / f"{version}.json"

    def read_state() -> dict[str, Any] | None:
        try:
            if state_path.is_symlink() or not state_path.is_file():
                return None
            value = json.loads(state_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, ValueError):
            return None

    existing = read_state()
    if existing and existing.get("status") == "completed":
        completed_result = {
            "message": "Signed system update completed",
            "version": version,
            "release": existing.get("release"),
            "backup": existing.get("backup"),
            "exit_code": 0,
            "resumed": True,
        }
        return completed_result

    if checkpoint.get("stage") != "external-update-started":
        context.progress(
            5,
            f"Starting signed update {version}",
            checkpoint={"stage": "starting", "version": version},
            save_checkpoint=True,
        )
        request = run_privileged("request-update", version, timeout=30)
        if request.returncode != 0:
            detail = request.stderr or request.stdout or "Unable to start update unit"
            raise RuntimeError(detail.strip())
        context.progress(
            10,
            "Update delegated to the independent system unit",
            checkpoint={"stage": "external-update-started", "version": version},
            save_checkpoint=True,
        )

    progress_by_status = {
        "verifying": (15, "Verifying release signature"),
        "installing": (40, "Building immutable release"),
        "checking": (80, "Checking the new release"),
    }
    last_status = None
    while True:
        try:
            context.check_cancelled()
        except JobCancelledError:
            run_privileged("cancel-update", version, timeout=30)
            raise
        state = read_state()
        if state:
            status = state.get("status")
            if status == "completed":
                completed_result = {
                    "message": "Signed system update completed",
                    "version": version,
                    "release": state.get("release"),
                    "backup": state.get("backup"),
                    "exit_code": int(state.get("exit_code", 0)),
                }
                if completed_result["exit_code"] != 0:
                    raise RuntimeError("Updater reported completion with a non-zero exit code")
                context.progress(
                    95,
                    "Signed system update completed",
                    checkpoint={"stage": "completed", "result": completed_result},
                    save_checkpoint=True,
                )
                return completed_result
            if status == "failed":
                exit_code = int(state.get("exit_code", 1) or 1)
                detail = str(state.get("error") or "Signed system update failed")
                raise RuntimeError(f"Updater exited with code {exit_code}: {detail}")
            if status != last_status and status in progress_by_status:
                progress, message = progress_by_status[status]
                context.progress(
                    progress,
                    message,
                    checkpoint={
                        "stage": "external-update-started",
                        "version": version,
                        "updater_status": status,
                    },
                    save_checkpoint=True,
                )
                last_status = status
        time.sleep(2)


TASK_HANDLERS: dict[str, TaskHandler] = {
    "backup": _backup,
    "backup_restore": _backup_restore,
    "backup_verify": _backup_verify,
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
