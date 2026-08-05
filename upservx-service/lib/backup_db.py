"""
SQLite Database setup and management for backup system.
"""

import sqlite3
import os
import base64
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import logging

from lib.secure_store import ensure_config_directory

logger = logging.getLogger(__name__)

CONFIG_DIR = os.getenv("UPSERVX_CONFIG_DIR", "/etc/upservx")
BACKUP_DIR = os.path.join(CONFIG_DIR, "backup")
DATABASE_PATH = os.path.join(BACKUP_DIR, "backup.db")

class BackupDatabase:
    """SQLite database manager for backup system."""
    
    def __init__(self, db_path: str = DATABASE_PATH, legacy_servers_path: Optional[str] = None):
        self.db_path = db_path
        self.legacy_servers_path = legacy_servers_path or os.path.join(
            os.path.dirname(db_path), "backup_servers.json"
        )
        root_legacy = os.path.join(CONFIG_DIR, "backup_servers.json")
        if (
            db_path == DATABASE_PATH
            and not os.path.exists(self.legacy_servers_path)
            and os.path.exists(root_legacy)
        ):
            self.legacy_servers_path = root_legacy
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables."""
        # Ensure backup directory exists
        ensure_config_directory(os.path.dirname(self.db_path) or ".")
        
        # Migrate old database if it exists in old location
        old_db_path = os.path.join(CONFIG_DIR, "backup.db")
        if (
            self.db_path == DATABASE_PATH
            and old_db_path != self.db_path
            and os.path.exists(old_db_path)
            and not os.path.exists(self.db_path)
        ):
            import shutil
            try:
                shutil.move(old_db_path, self.db_path)
                logger.info(f"Migrated backup database from {old_db_path} to {self.db_path}")
            except Exception as e:
                logger.warning(f"Could not migrate backup database: {e}")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    type TEXT NOT NULL CHECK (type IN ('local', 'remote')),
                    status TEXT DEFAULT 'disconnected' CHECK (status IN ('connected', 'disconnected', 'error')),
                    host TEXT,
                    port INTEGER,
                    remote_path TEXT,
                    local_path TEXT,
                    auth_type TEXT CHECK (auth_type IN ('password', 'ssh_key', NULL)),
                    username TEXT,
                    password_encrypted TEXT,
                    ssh_key_path TEXT,
                    ssh_key_passphrase_encrypted TEXT,
                    capacity_gb REAL,
                    used_gb REAL,
                    last_sync TIMESTAMP,
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    backup_type TEXT NOT NULL CHECK (backup_type IN ('vm', 'container', 'system', 'database')),
                    targets TEXT NOT NULL, -- JSON array of target paths/names
                    schedule TEXT NOT NULL,
                    server_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'error')),
                    last_run TIMESTAMP,
                    next_run TIMESTAMP,
                    last_size INTEGER,
                    retention_days INTEGER DEFAULT 30,
                    compression BOOLEAN DEFAULT 1,
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (server_id) REFERENCES backup_servers (id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_instances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    server_id INTEGER NOT NULL,
                    backup_name TEXT NOT NULL,
                    backup_path TEXT NOT NULL,
                    backup_size INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'failed')),
                    backup_type TEXT NOT NULL,
                    targets TEXT, -- JSON array
                    error_message TEXT,
                    checksum_sha256 TEXT,
                    integrity_status TEXT DEFAULT 'pending',
                    verified_at TIMESTAMP,
                    last_test_restore TIMESTAMP,
                    started TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed TIMESTAMP,
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES backup_jobs (id) ON DELETE CASCADE,
                    FOREIGN KEY (server_id) REFERENCES backup_servers (id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Additive migrations keep existing installations usable without a
            # destructive schema rebuild.
            instance_columns = {
                row[1] for row in cursor.execute("PRAGMA table_info(backup_instances)")
            }
            for column, definition in (
                ("checksum_sha256", "TEXT"),
                ("integrity_status", "TEXT DEFAULT 'pending'"),
                ("verified_at", "TIMESTAMP"),
                ("last_test_restore", "TIMESTAMP"),
            ):
                if column not in instance_columns:
                    cursor.execute(
                        f"ALTER TABLE backup_instances ADD COLUMN {column} {definition}"
                    )
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_jobs_server_id ON backup_jobs (server_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_instances_job_id ON backup_instances (job_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_instances_server_id ON backup_instances (server_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_instances_status ON backup_instances (status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_backup_instances_created ON backup_instances (created DESC)")
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS update_backup_servers_timestamp 
                AFTER UPDATE ON backup_servers
                BEGIN
                    UPDATE backup_servers SET updated = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS update_backup_jobs_timestamp 
                AFTER UPDATE ON backup_jobs
                BEGIN
                    UPDATE backup_jobs SET updated = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END
            """)
            
            conn.commit()
            os.chmod(self.db_path, 0o600)
            self._migrate_legacy_sqlite_credentials(conn)
            self._migrate_legacy_servers(conn)
            logger.info("Database initialized successfully")

    @staticmethod
    def _normalize_server_status(status: Any) -> str:
        """Map legacy server states to the canonical connection states."""
        value = str(status or "disconnected").lower()
        if value == "active":
            return "disconnected"
        if value not in {"connected", "disconnected", "error"}:
            return "disconnected"
        return value

    def _migrate_legacy_sqlite_credentials(self, conn: sqlite3.Connection) -> None:
        """Convert credentials encrypted with the retired backup-only key."""

        cursor = conn.cursor()
        marker = "legacy_backup_cipher_migrated"
        if cursor.execute(
            "SELECT 1 FROM backup_metadata WHERE key = ?", (marker,)
        ).fetchone():
            return
        legacy_key_path = os.path.join(os.path.dirname(self.db_path), "backup_key")
        if not os.path.exists(legacy_key_path):
            cursor.execute(
                "INSERT INTO backup_metadata (key, value) VALUES (?, ?)",
                (marker, datetime.now().isoformat()),
            )
            conn.commit()
            return
        if os.path.islink(legacy_key_path) or not os.path.isfile(legacy_key_path):
            raise RuntimeError("Unsafe legacy backup encryption key path")

        from cryptography.fernet import Fernet
        from lib.encryption import get_encryption_manager

        with open(legacy_key_path, "rb") as handle:
            legacy_cipher = Fernet(handle.read().strip())
        canonical_cipher = get_encryption_manager()
        try:
            rows = cursor.execute(
                """
                SELECT id, password_encrypted, ssh_key_passphrase_encrypted
                FROM backup_servers
                """
            ).fetchall()
            for row in rows:
                updates: Dict[str, str] = {}
                for field in (
                    "password_encrypted",
                    "ssh_key_passphrase_encrypted",
                ):
                    ciphertext = row[field]
                    if not ciphertext:
                        continue
                    try:
                        canonical_cipher.decrypt(ciphertext)
                        continue
                    except ValueError:
                        pass
                    try:
                        wrapped_token = base64.b64decode(
                            ciphertext.encode("ascii"), validate=True
                        )
                        plaintext = legacy_cipher.decrypt(wrapped_token).decode("utf-8")
                    except Exception as error:
                        raise ValueError(
                            f"Could not migrate backup credential for server {row['id']}"
                        ) from error
                    updates[field] = canonical_cipher.encrypt(plaintext)
                if updates:
                    assignments = ", ".join(f"{field} = ?" for field in updates)
                    cursor.execute(
                        f"UPDATE backup_servers SET {assignments} WHERE id = ?",
                        (*updates.values(), row["id"]),
                    )
            cursor.execute(
                "INSERT INTO backup_metadata (key, value) VALUES (?, ?)",
                (marker, datetime.now().isoformat()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _migrate_legacy_servers(self, conn: sqlite3.Connection) -> None:
        """Import the old JSON server store once, preserving server IDs.

        Legacy encrypted passwords were written with ``lib.encryption`` and are
        copied as ciphertext. Plaintext legacy values are deliberately ignored.
        """
        cursor = conn.cursor()
        migrated = cursor.execute(
            "SELECT value FROM backup_metadata WHERE key = 'legacy_servers_imported'"
        ).fetchone()
        if migrated or not os.path.exists(self.legacy_servers_path):
            return

        try:
            with open(self.legacy_servers_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            servers = payload.get("servers", []) if isinstance(payload, dict) else []
            if not isinstance(servers, list):
                raise ValueError("legacy backup server data is not a list")

            for server in servers:
                if not isinstance(server, dict) or not server.get("name"):
                    continue
                password_encrypted = None
                if (
                    isinstance(server.get("password"), str)
                    and server.get("password")
                    and server.get("password_encrypted") is True
                ):
                    password_encrypted = server["password"]
                passphrase_encrypted = server.get("ssh_key_passphrase_encrypted")
                if not isinstance(passphrase_encrypted, str):
                    legacy_passphrase = server.get("ssh_key_passphrase")
                    if isinstance(legacy_passphrase, str) and legacy_passphrase:
                        from lib.encryption import get_encryption_manager

                        passphrase_encrypted = get_encryption_manager().encrypt(
                            legacy_passphrase
                        )
                    else:
                        passphrase_encrypted = None
                server_type = "remote" if server.get("type") == "remote" else "local"
                local_path = server.get("local_path")
                remote_path = server.get("remote_path")
                if server_type == "local" and (
                    not isinstance(local_path, str) or not os.path.isabs(local_path)
                ):
                    local_path = "/var/lib/upservx/backups"
                if server_type == "remote" and (
                    not isinstance(remote_path, str) or not remote_path.startswith("/")
                ):
                    remote_path = "/backups"
                values = (
                    server["name"],
                    server_type,
                    self._normalize_server_status(server.get("status")),
                    server.get("host"), server.get("port"), remote_path,
                    local_path,
                    server.get("auth_type")
                    if server.get("auth_type") in {"password", "ssh_key"}
                    else None,
                    server.get("username"), password_encrypted,
                    server.get("ssh_key_path"), passphrase_encrypted,
                    server.get("created") or datetime.now().isoformat(),
                    server.get("updated") or datetime.now().isoformat(),
                )
                same_name = cursor.execute(
                    "SELECT id FROM backup_servers WHERE name = ?", (server["name"],)
                ).fetchone()
                requested_id = server.get("id")
                id_taken = (
                    cursor.execute(
                        "SELECT id FROM backup_servers WHERE id = ?", (requested_id,)
                    ).fetchone()
                    if requested_id is not None
                    else None
                )
                if same_name:
                    # SQLite wins on conflicts, but fill fields that only
                    # existed in the legacy JSON store (especially credentials).
                    cursor.execute(
                        """
                        UPDATE backup_servers SET
                            host = COALESCE(host, ?), port = COALESCE(port, ?),
                            remote_path = COALESCE(remote_path, ?),
                            local_path = COALESCE(local_path, ?),
                            auth_type = COALESCE(auth_type, ?),
                            username = COALESCE(username, ?),
                            password_encrypted = COALESCE(password_encrypted, ?),
                            ssh_key_path = COALESCE(ssh_key_path, ?),
                            ssh_key_passphrase_encrypted =
                                COALESCE(ssh_key_passphrase_encrypted, ?)
                        WHERE id = ?
                        """,
                        (*values[3:12], same_name["id"]),
                    )
                    if requested_id is not None and not id_taken:
                        cursor.execute(
                            "UPDATE backup_jobs SET server_id = ? WHERE server_id = ?",
                            (same_name["id"], requested_id),
                        )
                        cursor.execute(
                            "UPDATE backup_instances SET server_id = ? WHERE server_id = ?",
                            (same_name["id"], requested_id),
                        )
                    continue

                columns = """
                    name, type, status, host, port, remote_path, local_path,
                    auth_type, username, password_encrypted, ssh_key_path,
                    ssh_key_passphrase_encrypted, created, updated
                """
                if requested_id is not None and not id_taken:
                    cursor.execute(
                        f"INSERT INTO backup_servers (id, {columns}) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (requested_id, *values),
                    )
                else:
                    cursor.execute(
                        f"INSERT INTO backup_servers ({columns}) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        values,
                    )

            cursor.execute(
                "INSERT OR REPLACE INTO backup_metadata (key, value) VALUES (?, ?)",
                ("legacy_servers_imported", datetime.now().isoformat()),
            )
            conn.commit()
            migrated_path = f"{self.legacy_servers_path}.migrated"
            if not os.path.exists(migrated_path):
                os.replace(self.legacy_servers_path, migrated_path)
            logger.info("Imported legacy backup servers into SQLite")
        except Exception as error:
            conn.rollback()
            logger.warning("Could not import legacy backup servers: %s", error)
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper error handling."""
        conn = sqlite3.connect(self.db_path)
        os.chmod(self.db_path, 0o600)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    # Backup Servers CRUD Operations
    def create_backup_server(self, server_data: Dict[str, Any]) -> int:
        """Create a new backup server."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO backup_servers (
                    name, type, status, host, port, remote_path, local_path,
                    auth_type, username, password_encrypted, ssh_key_path, 
                    ssh_key_passphrase_encrypted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                server_data['name'],
                server_data['type'],
                self._normalize_server_status(server_data.get('status')),
                server_data.get('host'),
                server_data.get('port'),
                server_data.get('remote_path'),
                server_data.get('local_path'),
                server_data.get('auth_type'),
                server_data.get('username'),
                server_data.get('password_encrypted'),
                server_data.get('ssh_key_path'),
                server_data.get('ssh_key_passphrase_encrypted')
            ))
            
            server_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Created backup server: {server_data['name']} (ID: {server_id})")
            return server_id
    
    def get_backup_servers(self) -> List[Dict[str, Any]]:
        """Get all backup servers."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backup_servers ORDER BY created DESC")
            
            servers = []
            for row in cursor.fetchall():
                server = dict(row)
                # Don't return encrypted passwords in API responses
                server.pop('password_encrypted', None)
                server.pop('ssh_key_passphrase_encrypted', None)
                servers.append(server)
            
            return servers
    
    def get_backup_server(
        self,
        server_id: int,
        *,
        include_secrets: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Get a specific backup server by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backup_servers WHERE id = ?", (server_id,))
            
            row = cursor.fetchone()
            if row:
                server = dict(row)
                if not include_secrets:
                    server.pop('password_encrypted', None)
                    server.pop('ssh_key_passphrase_encrypted', None)
                return server
            return None
    
    def update_backup_server(self, server_id: int, update_data: Dict[str, Any]) -> bool:
        """Update a backup server."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            set_clauses = []
            values = []
            
            for field in ['name', 'type', 'status', 'host', 'port', 'remote_path', 
                         'local_path', 'auth_type', 'username', 'password_encrypted', 
                         'ssh_key_path', 'ssh_key_passphrase_encrypted', 'capacity_gb', 
                         'used_gb', 'last_sync']:
                if field in update_data:
                    set_clauses.append(f"{field} = ?")
                    values.append(
                        self._normalize_server_status(update_data[field])
                        if field == "status" else update_data[field]
                    )
            
            if not set_clauses:
                return False
            
            values.append(server_id)
            query = f"UPDATE backup_servers SET {', '.join(set_clauses)} WHERE id = ?"
            
            cursor.execute(query, values)
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Updated backup server ID: {server_id}")
            
            return success
    
    def delete_backup_server(self, server_id: int) -> bool:
        """Delete an unused backup server without cascading backup history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM backup_jobs WHERE server_id = ? LIMIT 1", (server_id,))
            if cursor.fetchone():
                raise ValueError("Backup server is still referenced by backup jobs")
            cursor.execute(
                "SELECT 1 FROM backup_instances WHERE server_id = ? LIMIT 1",
                (server_id,),
            )
            if cursor.fetchone():
                raise ValueError("Backup server is still referenced by backup archives")
            cursor.execute("DELETE FROM backup_servers WHERE id = ?", (server_id,))
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Deleted backup server ID: {server_id}")
            
            return success
    
    # Backup Jobs CRUD Operations
    def create_backup_job(self, job_data: Dict[str, Any]) -> int:
        """Create a new backup job."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            targets_json = json.dumps(job_data['targets'])
            
            cursor.execute("""
                INSERT INTO backup_jobs (
                    name, backup_type, targets, schedule, server_id, 
                    retention_days, compression
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                job_data['name'],
                job_data['backup_type'],
                targets_json,
                job_data['schedule'],
                job_data['server_id'],
                job_data.get('retention_days', 30),
                job_data.get('compression', True)
            ))
            
            job_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Created backup job: {job_data['name']} (ID: {job_id})")
            return job_id
    
    def get_backup_jobs(self) -> List[Dict[str, Any]]:
        """Get all backup jobs."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backup_jobs ORDER BY created DESC")
            
            jobs = []
            for row in cursor.fetchall():
                job = dict(row)
                job['targets'] = json.loads(job['targets']) if job['targets'] else []
                jobs.append(job)
            
            return jobs
    
    def get_backup_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific backup job by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backup_jobs WHERE id = ?", (job_id,))
            
            row = cursor.fetchone()
            if row:
                job = dict(row)
                job['targets'] = json.loads(job['targets']) if job['targets'] else []
                return job
            return None
    
    def update_backup_job(self, job_id: int, update_data: Dict[str, Any]) -> bool:
        """Update a backup job."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if 'targets' in update_data:
                update_data['targets'] = json.dumps(update_data['targets'])
            
            set_clauses = []
            values = []
            
            for field in ['name', 'backup_type', 'targets', 'schedule', 'server_id', 
                         'status', 'last_run', 'next_run', 'last_size', 'retention_days', 'compression']:
                if field in update_data:
                    set_clauses.append(f"{field} = ?")
                    values.append(update_data[field])
            
            if not set_clauses:
                return False
            
            values.append(job_id)
            query = f"UPDATE backup_jobs SET {', '.join(set_clauses)} WHERE id = ?"
            
            cursor.execute(query, values)
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Updated backup job ID: {job_id}")
            
            return success
    
    def delete_backup_job(self, job_id: int) -> bool:
        """Delete a backup job and all associated instances."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM backup_jobs WHERE id = ?", (job_id,))
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Deleted backup job ID: {job_id}")
            
            return success
    
    # Backup Instances CRUD Operations
    def create_backup_instance(self, instance_data: Dict[str, Any]) -> int:
        """Create a new backup instance."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            targets_json = json.dumps(instance_data.get('targets', []))
            
            cursor.execute("""
                INSERT INTO backup_instances (
                    job_id, server_id, backup_name, backup_path, backup_size,
                    status, backup_type, targets, error_message, checksum_sha256,
                    integrity_status, verified_at, last_test_restore, started, completed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                instance_data['job_id'],
                instance_data['server_id'],
                instance_data['backup_name'],
                instance_data['backup_path'],
                instance_data.get('backup_size', 0),
                instance_data.get('status', 'in_progress'),
                instance_data['backup_type'],
                targets_json,
                instance_data.get('error_message'),
                instance_data.get('checksum_sha256'),
                instance_data.get('integrity_status', 'pending'),
                instance_data.get('verified_at'),
                instance_data.get('last_test_restore'),
                instance_data.get('started'),
                instance_data.get('completed')
            ))
            
            instance_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Created backup instance: {instance_data['backup_name']} (ID: {instance_id})")
            return instance_id
    
    def get_backup_instances(self, job_id: Optional[int] = None, server_id: Optional[int] = None, 
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get backup instances with optional filtering."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM backup_instances"
            conditions = []
            params = []
            
            if job_id:
                conditions.append("job_id = ?")
                params.append(job_id)
            
            if server_id:
                conditions.append("server_id = ?")
                params.append(server_id)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY created DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            
            instances = []
            for row in cursor.fetchall():
                instance = dict(row)
                instance['targets'] = json.loads(instance['targets']) if instance['targets'] else []
                instances.append(instance)
            
            return instances
    
    def get_backup_instance(self, instance_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific backup instance by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backup_instances WHERE id = ?", (instance_id,))
            
            row = cursor.fetchone()
            if row:
                instance = dict(row)
                instance['targets'] = json.loads(instance['targets']) if instance['targets'] else []
                return instance
            return None
    
    def update_backup_instance(self, instance_id: int, update_data: Dict[str, Any]) -> bool:
        """Update a backup instance."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if 'targets' in update_data:
                update_data['targets'] = json.dumps(update_data['targets'])
            
            set_clauses = []
            values = []
            
            for field in [
                'backup_path', 'backup_size', 'status', 'error_message', 'completed',
                'checksum_sha256', 'integrity_status', 'verified_at', 'last_test_restore',
            ]:
                if field in update_data:
                    set_clauses.append(f"{field} = ?")
                    values.append(update_data[field])
            
            if not set_clauses:
                return False
            
            values.append(instance_id)
            query = f"UPDATE backup_instances SET {', '.join(set_clauses)} WHERE id = ?"
            
            cursor.execute(query, values)
            success = cursor.rowcount > 0
            conn.commit()
            
            return success
    
    def delete_backup_instance(self, instance_id: int) -> bool:
        """Delete a backup instance."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM backup_instances WHERE id = ?", (instance_id,))
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Deleted backup instance ID: {instance_id}")
            
            return success
    
    def cleanup_old_instances(self, retention_days: int = 90) -> int:
        """Refuse the former metadata-only cleanup operation."""
        raise RuntimeError(
            "Retention must delete each archive before its metadata; use "
            "get_expired_instances with BackupManager.delete_instance_archive"
        )

    def get_expired_instances(self, job_id: int, retention_days: int) -> List[Dict[str, Any]]:
        """Return completed/failed instances older than a job's retention window."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM backup_instances
                WHERE job_id = ?
                  AND status IN ('completed', 'failed')
                  AND created < datetime('now', ?)
                ORDER BY created ASC
                """,
                (job_id, f"-{max(0, int(retention_days))} days"),
            ).fetchall()
        instances = []
        for row in rows:
            instance = dict(row)
            instance['targets'] = json.loads(instance['targets']) if instance['targets'] else []
            instances.append(instance)
        return instances

backup_db = BackupDatabase()
