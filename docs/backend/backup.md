# Backup System

**Files:** `upservx-service/backup.py`, `upservx-service/backup_db.py`, `upservx-service/execute_backup.py`

**Required permission:** Admin (`sudo`/`wheel`)

---

## Overview

The backup system provides scheduled and on-demand backups for:

- Docker volumes
- Docker containers (via `docker export`)
- Virtual machines (via `virsh` snapshots / disk images)
- Directories
- A separate SQLite backup database

---

## Backup Database

The backup configuration is stored in a **separate SQLite database** (`/etc/upservx/backups.db`):

```python
# Models
class BackupJob(Base):
    __tablename__ = "backup_jobs"
    id: int (PK)
    name: str
    type: str              # "docker_volume", "docker_container", "vm", "directory"
    source: str            # Source to back up
    destination: str       # Backup target path
    schedule: str          # Cron expression
    retention_count: int   # Max. retained backups
    enabled: bool
    last_run: datetime
    last_status: str       # "success", "error", "running"
    created_at: datetime

class BackupResult(Base):
    __tablename__ = "backup_results"
    id: int (PK)
    job_id: int (FK → backup_jobs)
    started_at: datetime
    finished_at: datetime
    status: str            # "success", "error"
    size_bytes: int
    path: str
    error_message: str
```

---

## Backup Types

### Docker Volume
```bash
docker run --rm -v <volume>:/data -v <dest>:/backup   busybox tar czf /backup/<name>-<timestamp>.tar.gz /data
```

### Docker Container
```bash
docker export <container> | gzip > <dest>/<name>-<timestamp>.tar.gz
```

### Virtual Machine
```bash
virsh snapshot-create-as <vm> --disk-only --quiesce
# Copy disk image
virsh snapshot-delete <vm> <snapshot>
```

### Directory
```bash
tar czf <dest>/<name>-<timestamp>.tar.gz -C <source> .
```

---

## Scheduling

The backup system uses the **crontab manager** (`crontab_manager.py`) to register jobs. Each backup job gets its own cron entry:

```
*/30 * * * * /usr/local/bin/upservx-backup execute <job_id>
```

The cron expression is stored in the `BackupJob.schedule` field.

---

## Retention Management

When a backup succeeds, the system checks existing backups and deletes old ones based on `retention_count`:

```python
def cleanup_old_backups(job: BackupJob, dest_path: str):
    backups = sorted(glob.glob(f"{dest_path}/{job.name}-*.tar.gz"))
    while len(backups) > job.retention_count:
        os.remove(backups.pop(0))
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/backup/jobs` | All backup jobs |
| `POST` | `/backup/jobs` | Create new job |
| `GET` | `/backup/jobs/{id}` | Job details |
| `PUT` | `/backup/jobs/{id}` | Edit job |
| `DELETE` | `/backup/jobs/{id}` | Delete job |
| `POST` | `/backup/jobs/{id}/run` | Run job immediately |
| `GET` | `/backup/jobs/{id}/results` | Execution history |
| `GET` | `/backup/results` | All results |
