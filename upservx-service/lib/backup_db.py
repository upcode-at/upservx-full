"""
SQLite Database setup and management for backup system.
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

BACKUP_DIR = "/etc/upservx/backup"
DATABASE_PATH = os.path.join(BACKUP_DIR, "backup.db")

class BackupDatabase:
    """SQLite database manager for backup system."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with required tables."""
        # Ensure backup directory exists
        os.makedirs(BACKUP_DIR, mode=0o755, exist_ok=True)
        
        # Migrate old database if it exists in old location
        old_db_path = "/etc/upservx/backup.db"
        if old_db_path != self.db_path and os.path.exists(old_db_path) and not os.path.exists(self.db_path):
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
                    started TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed TIMESTAMP,
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (job_id) REFERENCES backup_jobs (id) ON DELETE CASCADE,
                    FOREIGN KEY (server_id) REFERENCES backup_servers (id) ON DELETE CASCADE
                )
            """)
            
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
            logger.info("Database initialized successfully")
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper error handling."""
        conn = sqlite3.connect(self.db_path)
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
            
            targets_json = json.dumps(server_data.get('targets', [])) if 'targets' in server_data else None
            
            cursor.execute("""
                INSERT INTO backup_servers (
                    name, type, host, port, remote_path, local_path, 
                    auth_type, username, password_encrypted, ssh_key_path, 
                    ssh_key_passphrase_encrypted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                server_data['name'],
                server_data['type'],
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
    
    def get_backup_server(self, server_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific backup server by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backup_servers WHERE id = ?", (server_id,))
            
            row = cursor.fetchone()
            if row:
                server = dict(row)
                # Don't return encrypted passwords
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
                    values.append(update_data[field])
            
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
        """Delete a backup server and all associated jobs."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
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
                    status, backup_type, targets, error_message, started, completed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            
            for field in ['backup_size', 'status', 'error_message', 'completed']:
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
        """Clean up old backup instances based on retention policy."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM backup_instances 
                WHERE created < datetime('now', '-{} days')
            """.format(retention_days))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old backup instances")
            
            return deleted_count

backup_db = BackupDatabase()