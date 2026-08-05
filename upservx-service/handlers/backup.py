"""
Backup management module supporting local and remote storage servers
with SSH key and password authentication.
"""

import os
import posixpath
import re
import shlex
import stat
import subprocess
import paramiko
import asyncio
import logging
import threading
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
import json
import io
import tarfile
import tempfile
import shutil
from pathlib import Path
import hashlib
import uuid
from contextlib import contextmanager
from lib.encryption import get_encryption_manager
from lib.logger import log_backup

try:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/tmp/backup_debug.log', mode='a')
        ]
    )
except PermissionError:
    # Fallback to console only if file logging fails
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
logger = logging.getLogger(__name__)

class BackupAuthConfig:
    """Configuration for backup server authentication."""
    
    def __init__(self, 
                 auth_type: str,  # 'password', 'ssh_key'
                 username: str,
                 password: Optional[str] = None,
                 ssh_key_path: Optional[str] = None,
                 ssh_key_passphrase: Optional[str] = None):
        self.auth_type = auth_type
        self.username = username
        self.password = password
        self.ssh_key_path = ssh_key_path
        self.ssh_key_passphrase = ssh_key_passphrase

class BackupStorage:
    """Base class for backup storage providers."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        
    async def connect(self) -> bool:
        """Connect to the storage backend."""
        raise NotImplementedError
        
    async def disconnect(self):
        """Disconnect from the storage backend."""
        raise NotImplementedError
        
    async def upload_backup(self, local_path: str, remote_path: str) -> bool:
        """Upload backup to storage."""
        raise NotImplementedError
        
    async def download_backup(self, remote_path: str, local_path: str) -> bool:
        """Download backup from storage."""
        raise NotImplementedError
        
    async def list_backups(self, path: str = "/") -> List[Dict[str, Any]]:
        """List available backups."""
        raise NotImplementedError
        
    async def delete_backup(self, remote_path: str) -> bool:
        """Delete backup from storage."""
        raise NotImplementedError
        
    async def get_storage_info(self) -> Dict[str, Any]:
        """Get storage capacity and usage information."""
        raise NotImplementedError

class LocalBackupStorage(BackupStorage):
    """Local filesystem backup storage."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.backup_path = config.get('path', '/var/lib/upservx/backups')
        
    async def connect(self) -> bool:
        """Verify local backup directory exists and is writable."""
        try:
            os.makedirs(self.backup_path, exist_ok=True)
            test_file = os.path.join(self.backup_path, '.test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except Exception as e:
            logger.error(f"Local backup storage connection failed: {e}")
            return False

    async def disconnect(self):
        """No-op for local storage."""
        pass
        
    async def upload_backup(self, local_path: str, remote_path: str) -> bool:
        """Copy backup to local storage directory."""
        try:
            full_remote_path = os.path.join(self.backup_path, remote_path.lstrip('/'))
            os.makedirs(os.path.dirname(full_remote_path), exist_ok=True)
            shutil.copy2(local_path, full_remote_path)
            return True
        except Exception as e:
            logger.error(f"Local backup upload failed: {e}")
            return False
            
    async def download_backup(self, remote_path: str, local_path: str) -> bool:
        """Copy backup from local storage to specified location."""
        try:
            full_remote_path = os.path.join(self.backup_path, remote_path.lstrip('/'))
            shutil.copy2(full_remote_path, local_path)
            return True
        except Exception as e:
            logger.error(f"Local backup download failed: {e}")
            return False
            
    async def list_backups(self, path: str = "/") -> List[Dict[str, Any]]:
        """List backups in local storage."""
        try:
            full_path = os.path.join(self.backup_path, path.lstrip('/'))
            backups = []
            
            if os.path.exists(full_path):
                for item in os.listdir(full_path):
                    item_path = os.path.join(full_path, item)
                    stat = os.stat(item_path)
                    backups.append({
                        'name': item,
                        'path': os.path.join(path, item),
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        'is_directory': os.path.isdir(item_path)
                    })
            return backups
        except Exception as e:
            logger.error(f"Failed to list local backups: {e}")
            return []
            
    async def delete_backup(self, remote_path: str) -> bool:
        """Delete backup from local storage."""
        try:
            full_path = os.path.join(self.backup_path, remote_path.lstrip('/'))
            if os.path.isfile(full_path):
                os.remove(full_path)
            elif os.path.isdir(full_path):
                shutil.rmtree(full_path)
            return True
        except Exception as e:
            logger.error(f"Failed to delete local backup: {e}")
            return False
            
    async def get_storage_info(self) -> Dict[str, Any]:
        """Get local storage information."""
        try:
            statvfs = os.statvfs(self.backup_path)
            total_bytes = statvfs.f_frsize * statvfs.f_blocks
            available_bytes = statvfs.f_frsize * statvfs.f_available
            used_bytes = total_bytes - available_bytes
            
            return {
                'type': 'local',
                'total_gb': round(total_bytes / (1024**3), 2),
                'used_gb': round(used_bytes / (1024**3), 2),
                'available_gb': round(available_bytes / (1024**3), 2),
                'usage_percent': round((used_bytes / total_bytes) * 100, 2)
            }
        except Exception as e:
            logger.error(f"Failed to get local storage info: {e}")
            return {}

class RemoteBackupStorage(BackupStorage):
    """Remote SSH/SFTP backup storage."""
    
    def __init__(self, name: str, config: Dict[str, Any], auth_config: BackupAuthConfig):
        super().__init__(name, config)
        self.host = config['host']
        self.port = config.get('port', 22)
        self.remote_path = config.get('remote_path', '/backups')
        self.auth_config = auth_config
        self.ssh_client = None
        self.sftp_client = None
        
    async def connect(self) -> bool:
        """Connect to remote server via SSH."""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.auth_config.auth_type == 'ssh_key':
                key_path = self.auth_config.ssh_key_path
                passphrase = self.auth_config.ssh_key_passphrase
                
                try:
                    key_classes = [
                        key_class
                        for name in ("RSAKey", "DSSKey", "ECDSAKey", "Ed25519Key")
                        if (key_class := getattr(paramiko, name, None)) is not None
                    ]
                    for key_class in key_classes:
                        try:
                            private_key = key_class.from_private_key_file(
                                key_path,
                                password=passphrase,
                            )
                            break
                        except Exception:
                            continue
                    else:
                        logger.error("Could not load SSH private key")
                        return False
                        
                    self.ssh_client.connect(
                        hostname=self.host,
                        port=self.port,
                        username=self.auth_config.username,
                        pkey=private_key,
                        timeout=10,
                        look_for_keys=False,
                        allow_agent=False,
                    )
                except Exception as e:
                    logger.error(f"SSH key authentication failed: {e}")
                    return False
                    
            elif self.auth_config.auth_type == 'password':
                self.ssh_client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.auth_config.username,
                    password=self.auth_config.password,
                    timeout=10,
                    look_for_keys=False,
                    allow_agent=False,
                )
            else:
                logger.error(f"Unsupported auth type: {self.auth_config.auth_type}")
                return False
                
            self.sftp_client = self.ssh_client.open_sftp()
            self._ensure_remote_directory(self.remote_path)
            return True
            
        except Exception as e:
            logger.error(f"Remote backup storage connection failed: {e}")
            if self.ssh_client:
                self.ssh_client.close()
            return False
            
    async def disconnect(self):
        """Disconnect from remote server."""
        if self.sftp_client:
            self.sftp_client.close()
        if self.ssh_client:
            self.ssh_client.close()

    def _ensure_remote_directory(self, directory: str) -> None:
        current = "/" if directory.startswith("/") else ""
        for component in (part for part in directory.split("/") if part):
            current = f"{current.rstrip('/')}/{component}"
            try:
                self.sftp_client.stat(current)
            except OSError:
                self.sftp_client.mkdir(current)
            
    async def upload_backup(self, local_path: str, remote_path: str) -> bool:
        """Upload backup to remote server."""
        try:
            full_remote_path = os.path.join(self.remote_path, remote_path.lstrip('/'))
            
            remote_dir = os.path.dirname(full_remote_path)
            self._ensure_remote_directory(remote_dir)
                
            self.sftp_client.put(local_path, full_remote_path)
            return True
        except Exception as e:
            logger.error(f"Remote backup upload failed: {e}")
            return False
            
    async def download_backup(self, remote_path: str, local_path: str) -> bool:
        """Download backup from remote server."""
        try:
            full_remote_path = os.path.join(self.remote_path, remote_path.lstrip('/'))
            self.sftp_client.get(full_remote_path, local_path)
            return True
        except Exception as e:
            logger.error(f"Remote backup download failed: {e}")
            return False
            
    async def list_backups(self, path: str = "/") -> List[Dict[str, Any]]:
        """List backups on remote server."""
        try:
            full_path = os.path.join(self.remote_path, path.lstrip('/'))
            backups = []
            
            try:
                items = self.sftp_client.listdir_attr(full_path)
                for item in items:
                    backups.append({
                        'name': item.filename,
                        'path': os.path.join(path, item.filename),
                        'size': item.st_size,
                        'modified': datetime.fromtimestamp(item.st_mtime).isoformat(),
                        'is_directory': item.st_mode is not None and 
                                      (item.st_mode & 0o170000) == 0o040000
                    })
            except Exception:
                pass  # Directory might not exist
                
            return backups
        except Exception as e:
            logger.error(f"Failed to list remote backups: {e}")
            return []
            
    async def delete_backup(self, remote_path: str) -> bool:
        """Delete backup from remote server."""
        try:
            full_path = os.path.join(self.remote_path, remote_path.lstrip('/'))
            
            try:
                stat = self.sftp_client.stat(full_path)
                if (stat.st_mode & 0o170000) == 0o040000:
                    # Backup instances always represent archive files. Refuse
                    # recursive remote deletion through this API.
                    logger.error("Refusing to recursively delete remote directory %s", full_path)
                    return False
                self.sftp_client.remove(full_path)
                return True
            except OSError as e:
                if getattr(e, "errno", None) == 2:
                    return True
                logger.error(f"Failed to delete remote backup: {e}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete remote backup: {e}")
            return False
            
    async def get_storage_info(self) -> Dict[str, Any]:
        """Get remote storage information via SSH command."""
        try:
            _stdin, stdout, stderr = self.ssh_client.exec_command(
                f"df -Pk -- {shlex.quote(self.remote_path)}"
            )
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            lines = output.split('\n')
            
            if len(lines) >= 2:
                fields = lines[1].split()
                if len(fields) >= 6:
                    total_bytes = int(fields[1]) * 1024
                    used_bytes = int(fields[2]) * 1024
                    available_bytes = int(fields[3]) * 1024
                    return {
                        'type': 'remote',
                        'total_gb': round(total_bytes / (1024 ** 3), 2),
                        'used_gb': round(used_bytes / (1024 ** 3), 2),
                        'available_gb': round(available_bytes / (1024 ** 3), 2),
                        'usage_percent': float(fields[4].rstrip('%')),
                        'mount_point': fields[5]
                    }
            if error:
                logger.error("Remote df failed: %s", error)
            return {}
        except Exception as e:
            logger.error(f"Failed to get remote storage info: {e}")
            return {}

class BackupManager:
    """Main backup management class."""
    
    def __init__(self):
        self.storage_backends = {}
            
    def encrypt_sensitive_data(self, data: str) -> str:
        """Compatibility wrapper around the application's canonical cipher."""
        try:
            return get_encryption_manager().encrypt(data)
        except Exception as error:
            raise RuntimeError("Failed to encrypt backup credentials") from error
            
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Compatibility wrapper around the application's canonical cipher."""
        try:
            return get_encryption_manager().decrypt(encrypted_data)
        except Exception as error:
            raise ValueError("Failed to decrypt backup credentials") from error
            
    def add_storage_backend(self, 
                           storage_id: str, 
                           storage_type: str,
                           config: Dict[str, Any],
                           auth_config: Optional[BackupAuthConfig] = None):
        """Add a new storage backend."""
        if storage_type == 'local':
            self.storage_backends[storage_id] = LocalBackupStorage(storage_id, config)
        elif storage_type == 'remote':
            if not auth_config:
                raise ValueError("Remote storage requires authentication configuration")
            self.storage_backends[storage_id] = RemoteBackupStorage(storage_id, config, auth_config)
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")

    @staticmethod
    def _sha256_file(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_archive_stem(name: str) -> str:
        """Convert a display name into one filename component."""
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("._")
        if not stem:
            raise ValueError("Backup job name cannot form a safe archive filename")
        return stem[:128]

    @staticmethod
    def _safe_resource_name(name: str, kind: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name):
            raise ValueError(f"Invalid {kind} name: {name!r}")
        return name

    @classmethod
    def _add_vm_disk(
        cls, archive: tarfile.TarFile, disk_path: str, archive_name: str
    ) -> int:
        """Add a regular image or raw block device as a regular tar member."""
        resolved_disk = os.path.realpath(disk_path)
        disk_stat = os.stat(resolved_disk, follow_symlinks=False)
        if stat.S_ISREG(disk_stat.st_mode):
            archive.add(
                resolved_disk,
                arcname=archive_name,
                filter=cls._safe_tar_filter,
            )
            return disk_stat.st_size
        if stat.S_ISBLK(disk_stat.st_mode):
            size_result = subprocess.run(
                ["blockdev", "--getsize64", resolved_disk],
                capture_output=True,
                text=True,
                check=False,
            )
            if size_result.returncode != 0:
                raise RuntimeError(
                    size_result.stderr.strip()
                    or f"Could not determine block-device size for {disk_path}"
                )
            size = int(size_result.stdout.strip())
            info = tarfile.TarInfo(archive_name)
            info.size = size
            info.mode = 0o600
            info.mtime = int(datetime.now().timestamp())
            with open(resolved_disk, "rb", buffering=0) as source:
                archive.addfile(info, source)
            return size
        raise ValueError(f"Unsupported VM disk source: {disk_path}")

    @staticmethod
    def _safe_tar_filter(member: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
        """Exclude link and special-file entries from newly created archives."""
        if member.issym() or member.islnk() or member.isdev() or member.isfifo():
            logger.warning("Skipping unsafe archive member %s", member.name)
            return None
        member.mode &= 0o777
        return member

    @staticmethod
    def _validated_members(
        archive: tarfile.TarFile,
        destination: str,
        *,
        overwrite: bool,
    ) -> List[tarfile.TarInfo]:
        """Validate every tar member before any data is extracted."""
        root = os.path.realpath(destination)
        members: List[tarfile.TarInfo] = []
        seen: set[str] = set()
        non_directories: set[str] = set()
        for member in archive.getmembers():
            name = member.name.replace("\\", "/")
            if not name or name.startswith("/"):
                raise ValueError(f"Unsafe absolute archive path: {member.name}")
            lexical_target = os.path.abspath(os.path.join(root, name))
            if os.path.commonpath((root, lexical_target)) != root:
                raise ValueError(f"Archive path traversal detected: {member.name}")
            relative = os.path.relpath(lexical_target, root)
            current = root
            components = relative.split(os.sep)
            for index, component in enumerate(components):
                current = os.path.join(current, component)
                if os.path.lexists(current):
                    if os.path.islink(current):
                        raise ValueError(
                            f"Restore through a symlink is not allowed: {current}"
                        )
                    if index < len(components) - 1 and not os.path.isdir(current):
                        raise FileExistsError(
                            f"Restore parent is not a directory: {current}"
                        )
            target = os.path.realpath(lexical_target)
            if os.path.commonpath((root, target)) != root:
                raise ValueError(f"Archive path traversal detected: {member.name}")
            if target in seen:
                raise ValueError(f"Duplicate archive path would overwrite data: {member.name}")
            seen.add(target)
            if member.issym() or member.islnk():
                raise ValueError(f"Archive links are not allowed: {member.name}")
            if member.isdev() or member.isfifo():
                raise ValueError(f"Archive special files are not allowed: {member.name}")
            if not member.isdir() and not member.isfile():
                raise ValueError(f"Unsupported archive member type: {member.name}")
            if os.path.lexists(target):
                if not overwrite:
                    raise FileExistsError(f"Restore target already exists: {target}")
                compatible = (member.isdir() and os.path.isdir(target)) or (
                    member.isfile() and os.path.isfile(target)
                )
                if not compatible:
                    raise FileExistsError(
                        f"Restore target has an incompatible type: {target}"
                    )
            # Never let archive metadata assign an attacker-controlled owner or
            # restore group/world-writable permissions when the service is root.
            member.uid = os.getuid()
            member.gid = os.getgid()
            member.uname = ""
            member.gname = ""
            member.mode &= 0o755
            if not member.isdir():
                non_directories.add(target)
            members.append(member)
        for target in seen:
            parent = os.path.dirname(target)
            while parent != root:
                if parent in non_directories:
                    raise ValueError(
                        f"Archive file would be used as a directory: {parent}"
                    )
                parent = os.path.dirname(parent)
        return members

    @classmethod
    def safe_extract_archive(
        cls,
        archive_path: str,
        destination: str,
        *,
        overwrite: bool = False,
    ) -> None:
        """Extract an archive without traversal, links, devices, or silent overwrite."""
        os.makedirs(destination, exist_ok=True)
        with tarfile.open(archive_path, "r:*") as archive:
            members = cls._validated_members(
                archive,
                destination,
                overwrite=overwrite,
            )
            archive.extractall(path=destination, members=members)

    @classmethod
    def verify_archive(
        cls,
        archive_path: str,
        expected_checksum: Optional[str] = None,
        *,
        test_restore: bool = True,
    ) -> Dict[str, Any]:
        """Verify checksum and readability, optionally performing an isolated restore."""
        checksum = cls._sha256_file(archive_path)
        if expected_checksum and checksum.lower() != expected_checksum.lower():
            raise ValueError("Backup checksum does not match metadata")
        validation_dir = tempfile.mkdtemp(prefix="upservx-verify-")
        try:
            with tarfile.open(archive_path, "r:*") as archive:
                cls._validated_members(archive, validation_dir, overwrite=False)
        finally:
            shutil.rmtree(validation_dir, ignore_errors=True)
        if test_restore:
            test_dir = tempfile.mkdtemp(prefix="upservx-test-restore-")
            try:
                cls.safe_extract_archive(archive_path, test_dir)
            finally:
                shutil.rmtree(test_dir, ignore_errors=True)
        return {"checksum_sha256": checksum, "integrity_status": "verified"}

    @staticmethod
    def _auth_from_server(server: Dict[str, Any]) -> BackupAuthConfig:
        return BackupAuthConfig(
            auth_type=server.get("auth_type") or "password",
            username=server.get("username") or "",
            password=server.get("password"),
            ssh_key_path=server.get("ssh_key_path"),
            ssh_key_passphrase=server.get("ssh_key_passphrase"),
        )

    def _storage_from_server(self, server: Dict[str, Any]) -> BackupStorage:
        if server["type"] == "local":
            # Instance paths are stored as absolute paths, so use filesystem root
            # as the storage base when operating on an existing instance.
            return LocalBackupStorage(str(server["id"]), {"path": "/"})
        return RemoteBackupStorage(
            str(server["id"]),
            {
                "host": server["host"],
                "port": server.get("port", 22),
                "remote_path": "/",
            },
            self._auth_from_server(server),
        )

    @staticmethod
    def _validated_instance_path(
        instance: Dict[str, Any], server: Dict[str, Any]
    ) -> str:
        """Ensure instance metadata cannot address files outside its destination."""
        path = instance.get("backup_path")
        if not path:
            return ""
        if server["type"] == "local":
            if os.path.islink(path):
                raise ValueError("Backup archive path is a symbolic link")
            candidate = os.path.realpath(path)
            configured_root = server.get("local_path")
            roots = (
                [configured_root]
                if configured_root
                else ["/var/lib/upservx/backups", "/tmp/backups"]
            )
            within_destination = any(
                os.path.commonpath((os.path.realpath(root), candidate))
                == os.path.realpath(root)
                for root in roots
            )
            if not os.path.isabs(path) or not within_destination:
                raise ValueError("Backup archive is outside its configured local path")
            return candidate
        root = posixpath.normpath(server.get("remote_path") or "/backups")
        candidate = posixpath.normpath(path)
        if not candidate.startswith("/") or posixpath.commonpath((root, candidate)) != root:
            raise ValueError("Backup archive is outside its configured remote path")
        return candidate

    @contextmanager
    def _local_archive(self, instance: Dict[str, Any], server: Dict[str, Any]):
        """Materialize a local or remote archive for verification/restoration."""
        archive_path = self._validated_instance_path(instance, server)
        if server["type"] == "local":
            if os.path.islink(archive_path) or not os.path.isfile(archive_path):
                raise ValueError("Backup archive path is not a regular file")
            yield archive_path
            return

        temp_dir = tempfile.mkdtemp(prefix="upservx-restore-")
        local_path = os.path.join(temp_dir, os.path.basename(archive_path))
        storage = self._storage_from_server(server)
        try:
            if not asyncio.run(storage.connect()):
                raise RuntimeError("Could not connect to backup server")
            if not asyncio.run(storage.download_backup(archive_path, local_path)):
                raise RuntimeError("Could not download backup archive")
            yield local_path
        finally:
            try:
                asyncio.run(storage.disconnect())
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def verify_instance(
        self,
        instance: Dict[str, Any],
        server: Dict[str, Any],
        *,
        test_restore: bool = True,
    ) -> Dict[str, Any]:
        with self._local_archive(instance, server) as archive_path:
            return self.verify_archive(
                archive_path,
                instance.get("checksum_sha256"),
                test_restore=test_restore,
            )

    def restore_instance(
        self,
        instance: Dict[str, Any],
        server: Dict[str, Any],
        restore_path: str,
        *,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Safely restore file, container-export, or VM assets to a destination."""
        if not os.path.isabs(restore_path):
            raise ValueError("Restore path must be absolute")
        with self._local_archive(instance, server) as archive_path:
            verification = self.verify_archive(
                archive_path,
                instance.get("checksum_sha256"),
                test_restore=False,
            )
            self.safe_extract_archive(
                archive_path,
                restore_path,
                overwrite=overwrite,
            )
        return {
            "success": True,
            "backup_type": instance["backup_type"],
            "restore_path": restore_path,
            **verification,
        }

    def delete_instance_archive(
        self,
        instance: Dict[str, Any],
        server: Dict[str, Any],
    ) -> bool:
        """Delete the archive represented by an instance from local or SFTP storage."""
        path = self._validated_instance_path(instance, server)
        if not path:
            return True
        if server["type"] == "local":
            if not os.path.lexists(path):
                return True
            if os.path.islink(path) or not os.path.isfile(path):
                raise ValueError("Backup archive path is not a regular file")
            os.unlink(path)
            return True
        storage = self._storage_from_server(server)
        if not asyncio.run(storage.connect()):
            return False
        try:
            return asyncio.run(storage.delete_backup(path))
        finally:
            asyncio.run(storage.disconnect())

    @contextmanager
    def _consistent_vm_disks(self, vm_name: str):
        """Yield stable VM disk paths using a quiesced external libvirt snapshot."""
        listing = subprocess.run(
            ["virsh", "domblklist", vm_name, "--details"],
            capture_output=True,
            text=True,
            check=False,
        )
        if listing.returncode != 0:
            raise RuntimeError(listing.stderr.strip() or "Could not list VM disks")
        disks: List[tuple[str, str]] = []
        for line in listing.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] == "disk" and parts[3] != "-":
                disks.append((parts[2], parts[3]))
        if not disks:
            raise RuntimeError(f"No disks found for VM {vm_name}")

        state = subprocess.run(
            ["virsh", "domstate", vm_name], capture_output=True, text=True, check=False
        )
        running = state.returncode == 0 and "running" in state.stdout.lower()
        snapshotted = False
        if running:
            snapshot_name = f"upservx-backup-{uuid.uuid4().hex[:12]}"
            snapshot = subprocess.run(
                [
                    "virsh", "snapshot-create-as", vm_name, snapshot_name,
                    "--disk-only", "--atomic", "--quiesce", "--no-metadata",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if snapshot.returncode != 0:
                raise RuntimeError(
                    "VM backup requires a working QEMU Guest Agent and an atomic "
                    f"libvirt disk snapshot: {snapshot.stderr.strip()}"
                )
            snapshotted = True
        try:
            # After an external snapshot, the original sources are stable while
            # the guest continues writing to overlay disks.
            yield [path for _target, path in disks]
        finally:
            if snapshotted:
                failures = []
                for target, _path in disks:
                    commit = subprocess.run(
                        [
                            "virsh", "blockcommit", vm_name, target,
                            "--active", "--pivot", "--wait",
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if commit.returncode != 0:
                        failures.append(f"{target}: {commit.stderr.strip()}")
                if failures:
                    raise RuntimeError(
                        "Could not merge VM backup snapshot overlays: " + "; ".join(failures)
                    )
            
    async def create_backup(self, 
                           backup_type: str,  # 'vm', 'container', 'system'
                           source_paths: List[str],
                           storage_id: str,
                           backup_name: str,
                           compression: bool = True) -> Dict[str, Any]:
        """Create a backup of specified sources."""
        if storage_id not in self.storage_backends:
            raise ValueError(f"Unknown storage backend: {storage_id}")
            
        storage = self.storage_backends[storage_id]
        
        if not await storage.connect():
            raise Exception("Failed to connect to storage backend")
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_filename = f"{self._safe_archive_stem(backup_name)}_{timestamp}.tar"
            if compression:
                backup_filename += ".gz"
                
            temp_dir = tempfile.mkdtemp()
            temp_backup_path = os.path.join(temp_dir, backup_filename)
            
            mode = "w:gz" if compression else "w"
            with tarfile.open(temp_backup_path, mode) as tar:
                for source_path in source_paths:
                    if not os.path.exists(source_path):
                        raise FileNotFoundError(
                            f"Backup target does not exist: {source_path}"
                        )
                    resolved_source = os.path.realpath(source_path)
                    if os.path.islink(source_path):
                        raise ValueError(
                            f"Backup target cannot be a symbolic link: {source_path}"
                        )
                    tar.add(
                        resolved_source,
                        arcname=resolved_source.lstrip('/'),
                        filter=self._safe_tar_filter,
                    )
                        
            backup_size = os.path.getsize(temp_backup_path)
            verification = self.verify_archive(temp_backup_path, test_restore=True)
            
            remote_path = f"{backup_type}/{backup_filename}"
            upload_success = await storage.upload_backup(temp_backup_path, remote_path)
            
            shutil.rmtree(temp_dir)
            
            if not upload_success:
                raise Exception("Failed to upload backup to storage")
                
            return {
                'success': True,
                'backup_name': backup_filename,
                'backup_path': remote_path,
                'backup_size': backup_size,
                'timestamp': timestamp,
                'storage_id': storage_id,
                **verification,
                'test_restore': True,
            }
            
        finally:
            await storage.disconnect()
            
    async def restore_backup(self, 
                           storage_id: str,
                           backup_path: str,
                           restore_path: str) -> bool:
        """Restore a backup from storage."""
        if storage_id not in self.storage_backends:
            raise ValueError(f"Unknown storage backend: {storage_id}")
            
        storage = self.storage_backends[storage_id]
        
        if not await storage.connect():
            return False
            
        try:
            temp_dir = tempfile.mkdtemp()
            temp_backup_path = os.path.join(temp_dir, os.path.basename(backup_path))
            
            if not await storage.download_backup(backup_path, temp_backup_path):
                return False
                
            self.verify_archive(temp_backup_path, test_restore=False)
            self.safe_extract_archive(
                temp_backup_path,
                restore_path,
                overwrite=False,
            )
                
            shutil.rmtree(temp_dir)
            return True
            
        except Exception as e:
            logger.error(f"Backup restore failed: {e}")
            return False
        finally:
            await storage.disconnect()
            
    async def list_backups(self, storage_id: str, path: str = "/") -> List[Dict[str, Any]]:
        """List available backups in storage."""
        if storage_id not in self.storage_backends:
            return []
            
        storage = self.storage_backends[storage_id]
        
        if not await storage.connect():
            return []
            
        try:
            return await storage.list_backups(path)
        finally:
            await storage.disconnect()
            
    async def delete_backup(self, storage_id: str, backup_path: str) -> bool:
        """Delete a backup from storage."""
        if storage_id not in self.storage_backends:
            return False
            
        storage = self.storage_backends[storage_id]
        
        if not await storage.connect():
            return False
            
        try:
            return await storage.delete_backup(backup_path)
        finally:
            await storage.disconnect()
            
    async def get_storage_info(self, storage_id: str) -> Dict[str, Any]:
        """Get storage information."""
        if storage_id not in self.storage_backends:
            return {}
            
        storage = self.storage_backends[storage_id]
        
        if not await storage.connect():
            return {}
            
        try:
            return await storage.get_storage_info()
        finally:
            await storage.disconnect()
    
    def execute_backup(
        self,
        job: Dict[str, Any],
        server: Dict[str, Any],
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        """Execute a backup job and create a compressed or plain tar archive."""
        try:
            def _progress(value: int, message: str) -> None:
                if progress_callback:
                    progress_callback(value, message)

            print("=" * 60)
            print("BACKUP DEBUG: Starting backup execution")
            print(f"BACKUP DEBUG: Job data: {job}")
            
            print(
                "BACKUP DEBUG: Server: "
                f"id={server.get('id', 'unknown')}, "
                f"name={server.get('name', 'unknown')}, "
                f"type={server.get('type', 'unknown')}"
            )
            
            logger.info(f"Starting backup execution for job: {job['name']}")
            log_backup(f"Starting backup job [{job['name']}]")
            _progress(5, "Backup started")
            
            if not job.get('targets'):
                error_msg = "No backup targets specified"
                print(f"BACKUP DEBUG ERROR: {error_msg}")
                return {'success': False, 'error': error_msg}
            
            print(f"BACKUP DEBUG: Backup targets: {job['targets']}")
            _progress(10, "Preparing backup targets")
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            suffix = ".tar.gz" if job.get("compression", True) else ".tar"
            backup_filename = f"{self._safe_archive_stem(job['name'])}_{timestamp}{suffix}"
            print(f"BACKUP DEBUG: Generated filename: {backup_filename}")
            
            if server['type'] == 'local':
                dest_dir = server.get('local_path') or '/var/lib/upservx/backups'
                backup_path = os.path.join(dest_dir, backup_filename)
                
                print(f"BACKUP DEBUG: Local backup destination: {dest_dir}")
                print(f"BACKUP DEBUG: Full backup path: {backup_path}")
                
                os.makedirs(dest_dir, exist_ok=True)
                print(f"BACKUP DEBUG: Created destination directory: {dest_dir}")
                
            else:  # remote server
                dest_dir = server.get('remote_path') or '/backups'
                backup_path = f"{dest_dir}/{backup_filename}"
                print(f"BACKUP DEBUG: Remote backup path: {backup_path}")
                
            logger.info(f"Creating backup archive: {backup_path}")
            _progress(20, "Creating archive")
            
            print("BACKUP DEBUG: Starting archive creation...")
            success, result = self._create_tar_backup(job, backup_path, server, progress_callback=_progress)
            print(f"BACKUP DEBUG: Tar creation result - Success: {success}, Result: {result}")
            
            if success:
                final_result = {
                    'success': True,
                    'backup_path': backup_path,
                    'size': result.get('size', 0),
                    'file_count': result.get('file_count', 0),
                    'compression_ratio': result.get('compression_ratio', 0),
                    'duration': result.get('duration', 0),
                    'checksum_sha256': result.get('checksum_sha256'),
                    'integrity_status': result.get('integrity_status', 'verified'),
                    'test_restore': result.get('test_restore', False),
                }
                print(f"BACKUP DEBUG: Final success result: {final_result}")
                log_backup(f"Backup job [{job['name']}] completed successfully — {result.get('file_count', 0)} files, {round(result.get('size', 0)/1024/1024, 2)} MB")
                _progress(100, "Backup completed successfully")
                return final_result
            else:
                error_result = {
                    'success': False,
                    'error': result.get('error', 'Unknown error during backup')
                }
                print(f"BACKUP DEBUG: Final error result: {error_result}")
                log_backup(f"Backup job [{job['name']}] failed: {result.get('error', 'Unknown error')}", error=True)
                _progress(100, f"Backup failed: {result.get('error', 'Unknown error')}")
                return error_result
                
        except Exception as e:
            print(f"BACKUP DEBUG EXCEPTION: {e}")
            import traceback
            print("BACKUP DEBUG TRACEBACK:")
            traceback.print_exc()
            logger.error(f"Backup execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_tar_backup(
        self,
        job: Dict[str, Any],
        backup_path: str,
        server: Dict[str, Any],
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> tuple:
        """Create a tar backup from job targets."""
        start_time = datetime.now()
        total_size = 0
        file_count = 0
        
        try:
            logger.info(f"Creating backup archive: {backup_path}")
            if progress_callback:
                progress_callback(25, "Daten werden gesammelt")
            
            if server['type'] == 'local':
                return self._create_local_tar_backup(job, backup_path, start_time, progress_callback=progress_callback)
            else:
                return self._create_remote_tar_backup(job, backup_path, server, start_time, progress_callback=progress_callback)
                
        except Exception as e:
            logger.error(f"Tar backup creation failed: {e}")
            return False, {'error': str(e)}
    
    def _create_local_tar_backup(
        self,
        job: Dict[str, Any],
        backup_path: str,
        start_time: datetime,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> tuple:
        """Create a local tar backup using the job's compression setting."""
        try:
            print("TAR DEBUG: Starting local tar creation")
            print(f"TAR DEBUG: Backup path: {backup_path}")
            print(f"TAR DEBUG: Job targets: {job['targets']}")
            
            total_size = 0
            file_count = 0

            if os.path.lexists(backup_path):
                raise FileExistsError(f"Backup archive already exists: {backup_path}")

            print("TAR DEBUG: Opening tar archive for writing...")
            compressed = bool(job.get("compression", True))
            mode = "w:gz" if compressed else "w"
            tar_kwargs = {"compresslevel": 6} if compressed else {}
            with tarfile.open(backup_path, mode, **tar_kwargs) as tar:
                print("TAR DEBUG: Tar file opened successfully")
                
                total_targets = max(1, len(job['targets']))
                for i, target in enumerate(job['targets']):
                    print(f"TAR DEBUG: Processing target {i+1}/{len(job['targets'])}: '{target}'")
                    if progress_callback:
                        pct = 30 + int((i / total_targets) * 50)
                        progress_callback(pct, f"Processing target {i + 1}/{len(job['targets'])}")
                    
                    if not target.strip():
                        print("TAR DEBUG: Skipping empty target")
                        continue
                        
                    logger.info(f"Adding to backup: {target}")
                    
                    if target.startswith('vm:'):
                        print(f"TAR DEBUG: Processing VM target: {target}")
                        vm_name = self._safe_resource_name(target[3:], "VM")
                        xml_content = None

                        xml_result = subprocess.run(
                            ["virsh", "dumpxml", vm_name],
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        if xml_result.returncode != 0:
                            raise RuntimeError(
                                xml_result.stderr.strip()
                                or f"Could not export VM definition for {vm_name}"
                            )
                        xml_content = xml_result.stdout
                        print(f"TAR DEBUG: Exported VM XML definition ({len(xml_content)} bytes)")

                        with self._consistent_vm_disks(vm_name) as vm_disk_paths:
                            if vm_disk_paths:
                                for disk_path in vm_disk_paths:
                                    disk_name = os.path.basename(disk_path)
                                    arcname = f"vms/{vm_name}/{disk_name}"
                                    print(f"TAR DEBUG: Adding disk {disk_path} as {arcname}")
                                    disk_size = self._add_vm_disk(
                                        tar, disk_path, arcname
                                    )
                                    total_size += disk_size
                                    file_count += 1
                                    print(f"TAR DEBUG: Added disk ({disk_size} bytes)")
                            else:
                                raise RuntimeError(f"No disk files found for VM '{vm_name}'")

                            if xml_content:
                                xml_bytes = xml_content.encode('utf-8')
                                xml_info = tarfile.TarInfo(name=f"vms/{vm_name}/{vm_name}.xml")
                                xml_info.size = len(xml_bytes)
                                xml_info.mtime = int(datetime.now().timestamp())
                                tar.addfile(xml_info, io.BytesIO(xml_bytes))
                                print(f"TAR DEBUG: Added VM XML definition to archive")
                            
                    elif target.startswith('container:'):
                        print(f"TAR DEBUG: Processing container target: {target}")
                        container_name = self._safe_resource_name(
                            target[10:], "container"
                        )
                        export_dir = tempfile.mkdtemp(prefix="upservx-container-")
                        try:
                            container_export_path = os.path.join(export_dir, "filesystem.tar")
                            print(f"TAR DEBUG: Exporting container to: {container_export_path}")
                            
                            result = subprocess.run([
                                'docker', 'export', container_name, '-o', container_export_path
                            ], capture_output=True, text=True, check=True)
                            
                            if os.path.exists(container_export_path):
                                print(f"TAR DEBUG: Container export successful, adding to archive")
                                total_size += os.path.getsize(container_export_path)
                                file_count += 1
                                tar.add(
                                    container_export_path,
                                    arcname=f"containers/{container_name}/filesystem.tar",
                                    filter=self._safe_tar_filter,
                                )
                                inspect = subprocess.run(
                                    ["docker", "inspect", container_name],
                                    capture_output=True,
                                    text=True,
                                    check=True,
                                )
                                inspect_bytes = inspect.stdout.encode("utf-8")
                                inspect_info = tarfile.TarInfo(
                                    name=f"containers/{container_name}/inspect.json"
                                )
                                inspect_info.size = len(inspect_bytes)
                                inspect_info.mtime = int(datetime.now().timestamp())
                                tar.addfile(inspect_info, io.BytesIO(inspect_bytes))
                                details = json.loads(inspect.stdout)[0]
                                for index, mount in enumerate(details.get("Mounts", [])):
                                    destination = mount.get("Destination")
                                    if not destination or not destination.startswith("/"):
                                        raise RuntimeError(
                                            f"Container mount {index} has no absolute destination"
                                        )
                                    volume_export = os.path.join(
                                        export_dir, f"volume-{index}"
                                    )
                                    subprocess.run(
                                        [
                                            "docker", "cp",
                                            f"{container_name}:{destination}",
                                            volume_export,
                                        ],
                                        capture_output=True,
                                        text=True,
                                        check=True,
                                    )
                                    for root, _directories, files in os.walk(volume_export):
                                        for filename in files:
                                            copied_path = os.path.join(root, filename)
                                            if not os.path.islink(copied_path):
                                                total_size += os.path.getsize(copied_path)
                                                file_count += 1
                                    tar.add(
                                        volume_export,
                                        arcname=(
                                            f"containers/{container_name}/volumes/{index}"
                                        ),
                                        filter=self._safe_tar_filter,
                                    )
                            else:
                                raise RuntimeError(
                                    f"Container export file was not created for {container_name}"
                                )
                                
                        except subprocess.CalledProcessError as e:
                            details = (e.stderr or e.stdout or str(e)).strip()
                            raise RuntimeError(
                                f"Could not export container {container_name}: {details}"
                            ) from e
                        finally:
                            shutil.rmtree(export_dir, ignore_errors=True)
                            
                    else:
                        print(f"TAR DEBUG: Processing regular path: {target}")
                        print(f"TAR DEBUG: Checking if path exists: {os.path.exists(target)}")
                        
                        source_path = os.path.realpath(target)
                        if os.path.islink(target):
                            raise ValueError(f"Backup target cannot be a symbolic link: {target}")
                        if os.path.exists(source_path):
                            if (
                                os.path.isdir(source_path)
                                and os.path.commonpath(
                                    (source_path, os.path.realpath(backup_path))
                                ) == source_path
                            ):
                                raise ValueError(
                                    "Backup archive destination cannot be inside a source directory"
                                )
                            print(f"TAR DEBUG: Path exists, calculating size...")
                            
                            if os.path.isfile(source_path):
                                size = os.path.getsize(source_path)
                                total_size += size
                                file_count += 1
                                print(f"TAR DEBUG: File size: {size} bytes")
                                
                            elif os.path.isdir(source_path):
                                print(f"TAR DEBUG: Directory found, walking files...")
                                dir_file_count = 0
                                dir_size = 0
                                
                                for root, dirs, files in os.walk(source_path):
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        try:
                                            file_size = os.path.getsize(file_path)
                                            total_size += file_size
                                            dir_size += file_size
                                            file_count += 1
                                            dir_file_count += 1
                                        except OSError as e:
                                            print(f"TAR DEBUG: Could not get size for {file_path}: {e}")
                                            pass
                                            
                                print(f"TAR DEBUG: Directory contains {dir_file_count} files, {dir_size} bytes")
                                            
                            arcname = source_path.lstrip('/')
                            print(f"TAR DEBUG: Adding to archive as: {arcname}")
                            tar.add(
                                source_path,
                                arcname=arcname,
                                filter=self._safe_tar_filter,
                            )
                            print(f"TAR DEBUG: Successfully added {target}")
                            
                        else:
                            raise FileNotFoundError(f"Backup target does not exist: {target}")
            
            print("TAR DEBUG: Tar archive creation completed")
            if progress_callback:
                progress_callback(85, "Archive created")
            
            if os.path.exists(backup_path):
                archive_size = os.path.getsize(backup_path)
                print(f"TAR DEBUG: Final archive size: {archive_size} bytes")
            else:
                print("TAR DEBUG ERROR: Archive file does not exist after creation!")
                return False, {'error': 'Archive file not created'}
            
            verification = self.verify_archive(backup_path, test_restore=True)
            compression_ratio = (total_size - archive_size) / total_size * 100 if total_size > 0 else 0
            duration = (datetime.now() - start_time).total_seconds()
            
            print(f"TAR DEBUG: Backup statistics:")
            print(f"  - Original size: {total_size} bytes")
            print(f"  - Archive size: {archive_size} bytes")  
            print(f"  - File count: {file_count}")
            print(f"  - Compression ratio: {compression_ratio:.1f}%")
            print(f"  - Duration: {duration:.2f}s")
            
            logger.info(f"Backup completed: {backup_path}")
            logger.info(f"Original size: {total_size} bytes, Archive size: {archive_size} bytes")
            logger.info(f"Compression ratio: {compression_ratio:.1f}%, Duration: {duration:.2f}s")
            
            return True, {
                'size': archive_size,
                'original_size': total_size,
                'file_count': file_count,
                'compression_ratio': compression_ratio,
                'duration': duration,
                **verification,
                'test_restore': True,
            }
            
        except Exception as e:
            print(f"TAR DEBUG EXCEPTION: {e}")
            import traceback
            print("TAR DEBUG TRACEBACK:")
            traceback.print_exc()
            
            logger.error(f"Local tar backup failed: {e}")
            if os.path.exists(backup_path):
                print(f"TAR DEBUG: Cleaning up incomplete archive: {backup_path}")
                os.unlink(backup_path)
            return False, {'error': str(e)}
    
    def _create_remote_tar_backup(
        self,
        job: Dict[str, Any],
        backup_path: str,
        server: Dict[str, Any],
        start_time: datetime,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> tuple:
        """Create and verify a remote tar backup via SFTP."""
        try:
            temp_dir = tempfile.mkdtemp()
            temp_archive = os.path.join(temp_dir, os.path.basename(backup_path))
            
            success, result = self._create_local_tar_backup(job, temp_archive, start_time, progress_callback=progress_callback)
            
            if not success:
                shutil.rmtree(temp_dir)
                return False, result
            
            if progress_callback:
                progress_callback(90, "Uploading archive to destination server")

            ssh_success = self._upload_to_remote_server(temp_archive, backup_path, server)
            
            shutil.rmtree(temp_dir)
            
            if ssh_success:
                # Verify what was actually persisted remotely, not only the
                # local staging file that was uploaded.
                try:
                    with self._local_archive(
                        {"backup_path": backup_path}, server
                    ) as downloaded_archive:
                        remote_verification = self.verify_archive(
                            downloaded_archive,
                            result.get("checksum_sha256"),
                            test_restore=True,
                        )
                    result.update(remote_verification)
                    result["test_restore"] = True
                except Exception:
                    try:
                        self.delete_instance_archive(
                            {"backup_path": backup_path}, server
                        )
                    except Exception:
                        logger.exception(
                            "Failed to remove a remote archive after verification failure"
                        )
                    raise
                return True, result
            else:
                return False, {'error': 'Failed to upload backup to remote server'}
                
        except Exception as e:
            logger.error(f"Remote tar backup failed: {e}")
            return False, {'error': str(e)}
    
    def _upload_to_remote_server(self, local_path: str, remote_path: str, server: Dict[str, Any]) -> bool:
        """Upload through the same SFTP storage adapter used by restore/delete."""
        storage = self._storage_from_server(server)
        try:
            if not asyncio.run(storage.connect()):
                return False
            uploaded = asyncio.run(storage.upload_backup(local_path, remote_path))
            if not uploaded:
                return False
            logger.info(f"Successfully uploaded backup to {server['host']}:{remote_path}")
            log_backup(f"Successfully uploaded backup to [{server['host']}]:{remote_path}")
            return True
        except Exception as e:
            logger.error(f"SSH upload failed: {e}")
            log_backup(f"SSH upload failed to [{server.get('host', 'unknown')}]: {e}", error=True)
            return False
        finally:
            try:
                asyncio.run(storage.disconnect())
            except Exception:
                logger.exception("Could not close remote backup connection")

_backup_manager_instance: Optional[BackupManager] = None
_backup_manager_lock = threading.Lock()


def get_backup_manager() -> BackupManager:
    """Initialize the backup manager on first use."""

    global _backup_manager_instance
    if _backup_manager_instance is None:
        with _backup_manager_lock:
            if _backup_manager_instance is None:
                _backup_manager_instance = BackupManager()
    return _backup_manager_instance


class _LazyBackupManager:
    def __getattr__(self, name):
        return getattr(get_backup_manager(), name)


backup_manager = _LazyBackupManager()
