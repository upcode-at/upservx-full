# Backup System

**Core files:** `upcode-harbor-service/api/backup.py`,
`upcode-harbor-service/handlers/backup.py`, `upcode-harbor-service/lib/backup_db.py`, and
`upcode-harbor-service/handlers/execute_backup.py`

**Required permission:** Admin (`sudo`/`wheel`)

## Architecture

Backup servers, jobs, credentials, and archive metadata use the single SQLite
database `/etc/upcode-harbor/backup/backup.db`. On first startup, the former
`backup_servers.json` store is imported and renamed with a `.migrated` suffix.
Credential ciphertext uses the application encryption key and is never returned
by public API responses.

Server connection status is one of `connected`, `disconnected`, or `error`.
Job scheduling status is independently one of `active`, `paused`, or `error`.

Cron entries call the Python interpreter running the installed service and the
real `handlers/execute_backup.py` entry point. Cron, the API, CLI `--run-now`,
and the UI all enqueue the same durable `backup` worker task. Editing an active
schedule replaces its existing entry; pausing or deleting a job removes it.

## Archive lifecycle

- Compression follows each job's `compression` setting (`.tar.gz` or `.tar`).
- Every completed archive receives a SHA-256 checksum, a readability check,
  and an isolated test extraction before it is marked verified.
- Remote archives are downloaded and verified after upload, so transfer
  corruption is detected.
- `retention_days` deletes the stored local/SFTP archive before deleting its
  metadata row.
- Deleting an instance or job also deletes its archive. Metadata remains when
  the storage deletion cannot be confirmed.
- Restore requests run in the persistent worker and stage file, container, or
  VM assets at an administrator-selected absolute path. Extraction rejects
  absolute/traversal paths, links, special files, duplicate members, symlinked
  destinations, and implicit overwrites.

Container archives contain the exported filesystem, Docker inspection data,
and mounted-volume data. VM archives contain the libvirt XML and disks. A
running VM must support a quiesced atomic external libvirt snapshot through the
QEMU Guest Agent; the guest continues running on overlay disks while stable base
images are archived, and the overlays are committed and pivoted afterward.

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET/POST` | `/backup/servers` | List/create destinations |
| `GET/PUT/DELETE` | `/backup/servers/{id}` | Read/update/delete an unused destination |
| `POST` | `/backup/servers/{id}/test` | Test connection and update status |
| `GET` | `/backup/servers/{id}/info` | Live capacity information |
| `GET/POST` | `/backup/jobs` | List/create jobs |
| `GET/PUT/DELETE` | `/backup/jobs/{id}` | Read/update/delete a job and its archives |
| `POST` | `/backup/jobs/{id}/execute` | Queue a durable run |
| `POST` | `/backup/jobs/{id}/trigger` | Compatibility alias for the same run path |
| `GET` | `/backup/jobs/{id}/progress` | Latest persistent job progress |
| `GET` | `/backup/instances` | List archive metadata |
| `GET/DELETE` | `/backup/instances/{id}` | Read or delete archive and metadata |
| `POST` | `/backup/instances/{id}/restore` | Queue verified safe extraction |
| `POST` | `/backup/instances/{id}/verify` | Queue checksum verification and test restore |

The request types consumed by the TypeScript client and CLI are generated from
FastAPI's OpenAPI schema with `tools/generate_api_contract.py`. Use `--check` in
CI to detect stale generated contracts.
