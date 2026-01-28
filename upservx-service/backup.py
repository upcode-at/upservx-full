"""
Backup management module supporting local and remote storage servers
with SSH key and password authentication.
"""

import os
import subprocess
import paramiko
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import tarfile
import tempfile
import shutil
from pathlib import Path
from cryptography.fernet import Fernet
import base64

# Enhanced logging configuration
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
        self.backup_path = config.get('path', '/var/backups')
        
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
                # Load private key
                key_path = self.auth_config.ssh_key_path
                passphrase = self.auth_config.ssh_key_passphrase
                
                try:
                    # Try different key types
                    for key_class in [paramiko.RSAKey, paramiko.DSSKey, paramiko.ECDSAKey, paramiko.Ed25519Key]:
                        try:
                            private_key = key_class.from_private_key_file(key_path, password=passphrase)
                            break
                        except paramiko.ssh_exception.PasswordRequiredException:
                            if not passphrase:
                                logger.error("SSH key requires passphrase")
                                return False
                            private_key = key_class.from_private_key_file(key_path, password=passphrase)
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
                        timeout=10
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
                    timeout=10
                )
            else:
                logger.error(f"Unsupported auth type: {self.auth_config.auth_type}")
                return False
                
            self.sftp_client = self.ssh_client.open_sftp()
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
            
    async def upload_backup(self, local_path: str, remote_path: str) -> bool:
        """Upload backup to remote server."""
        try:
            full_remote_path = os.path.join(self.remote_path, remote_path.lstrip('/'))
            
            # Ensure remote directory exists
            remote_dir = os.path.dirname(full_remote_path)
            try:
                self.sftp_client.makedirs(remote_dir)
            except Exception:
                pass  # Directory might already exist
                
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
            
            # Check if it's a file or directory
            try:
                stat = self.sftp_client.stat(full_path)
                if (stat.st_mode & 0o170000) == 0o040000:  # Directory
                    # Remove directory recursively via SSH command
                    self.ssh_client.exec_command(f'rm -rf "{full_path}"')
                else:  # File
                    self.sftp_client.remove(full_path)
                return True
            except Exception as e:
                logger.error(f"Failed to delete remote backup: {e}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete remote backup: {e}")
            return False
            
    async def get_storage_info(self) -> Dict[str, Any]:
        """Get remote storage information via SSH command."""
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(f'df -h "{self.remote_path}"')
            output = stdout.read().decode().strip()
            lines = output.split('\n')
            
            if len(lines) >= 2:
                # Parse df output
                fields = lines[1].split()
                if len(fields) >= 6:
                    return {
                        'type': 'remote',
                        'total': fields[1],
                        'used': fields[2],
                        'available': fields[3],
                        'usage_percent': fields[4],
                        'mount_point': fields[5]
                    }
            return {}
        except Exception as e:
            logger.error(f"Failed to get remote storage info: {e}")
            return {}


class BackupManager:
    """Main backup management class."""
    
    def __init__(self):
        self.storage_backends = {}
        self.encryption_key = self._get_or_create_encryption_key()
        
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for sensitive data."""
        key_file = '/etc/upservx/backup_key'
        try:
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            if os.path.exists(key_file):
                with open(key_file, 'rb') as f:
                    return f.read()
            else:
                key = Fernet.generate_key()
                with open(key_file, 'wb') as f:
                    f.write(key)
                os.chmod(key_file, 0o600)
                return key
        except Exception:
            # Fallback to memory-only key
            return Fernet.generate_key()
            
    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data like passwords."""
        try:
            fernet = Fernet(self.encryption_key)
            encrypted = fernet.encrypt(data.encode())
            return base64.b64encode(encrypted).decode()
        except Exception:
            return data  # Fallback to unencrypted
            
    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        try:
            fernet = Fernet(self.encryption_key)
            decoded = base64.b64decode(encrypted_data.encode())
            decrypted = fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception:
            return encrypted_data  # Assume it's not encrypted
            
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
        
        # Connect to storage
        if not await storage.connect():
            raise Exception("Failed to connect to storage backend")
            
        try:
            # Create temporary backup file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{backup_name}_{timestamp}.tar"
            if compression:
                backup_filename += ".gz"
                
            temp_dir = tempfile.mkdtemp()
            temp_backup_path = os.path.join(temp_dir, backup_filename)
            
            # Create tar archive
            mode = "w:gz" if compression else "w"
            with tarfile.open(temp_backup_path, mode) as tar:
                for source_path in source_paths:
                    if os.path.exists(source_path):
                        tar.add(source_path, arcname=os.path.basename(source_path))
                        
            # Get backup size
            backup_size = os.path.getsize(temp_backup_path)
            
            # Upload to storage
            remote_path = f"{backup_type}/{backup_filename}"
            upload_success = await storage.upload_backup(temp_backup_path, remote_path)
            
            # Cleanup temporary file
            shutil.rmtree(temp_dir)
            
            if not upload_success:
                raise Exception("Failed to upload backup to storage")
                
            return {
                'success': True,
                'backup_name': backup_filename,
                'backup_path': remote_path,
                'backup_size': backup_size,
                'timestamp': timestamp,
                'storage_id': storage_id
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
            # Download backup to temporary location
            temp_dir = tempfile.mkdtemp()
            temp_backup_path = os.path.join(temp_dir, os.path.basename(backup_path))
            
            if not await storage.download_backup(backup_path, temp_backup_path):
                return False
                
            # Extract backup
            with tarfile.open(temp_backup_path, 'r:*') as tar:
                tar.extractall(path=restore_path)
                
            # Cleanup
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
    
    def execute_backup(self, job: Dict[str, Any], server: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a backup job and create tar.gz archive."""
        try:
            print("=" * 60)
            print("BACKUP DEBUG: Starting backup execution")
            print(f"BACKUP DEBUG: Job data: {job}")
            print(f"BACKUP DEBUG: Server data: {server}")
            
            logger.info(f"Starting backup execution for job: {job['name']}")
            
            # Validate inputs
            if not job.get('targets'):
                error_msg = "No backup targets specified"
                print(f"BACKUP DEBUG ERROR: {error_msg}")
                return {'success': False, 'error': error_msg}
            
            print(f"BACKUP DEBUG: Backup targets: {job['targets']}")
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{job['name'].replace(' ', '_')}_{timestamp}.tar.gz"
            print(f"BACKUP DEBUG: Generated filename: {backup_filename}")
            
            # Determine destination path
            if server['type'] == 'local':
                dest_dir = server.get('local_path', '/tmp/backups')
                backup_path = os.path.join(dest_dir, backup_filename)
                
                print(f"BACKUP DEBUG: Local backup destination: {dest_dir}")
                print(f"BACKUP DEBUG: Full backup path: {backup_path}")
                
                # Ensure destination directory exists
                os.makedirs(dest_dir, exist_ok=True)
                print(f"BACKUP DEBUG: Created destination directory: {dest_dir}")
                
            else:  # remote server
                dest_dir = server.get('remote_path', '/backups')
                backup_path = f"{dest_dir}/{backup_filename}"
                print(f"BACKUP DEBUG: Remote backup path: {backup_path}")
                
            logger.info(f"Creating backup archive: {backup_path}")
            
            # Create tar.gz archive
            print("BACKUP DEBUG: Starting tar.gz creation...")
            success, result = self._create_tar_backup(job, backup_path, server)
            print(f"BACKUP DEBUG: Tar creation result - Success: {success}, Result: {result}")
            
            if success:
                final_result = {
                    'success': True,
                    'backup_path': backup_path,
                    'size': result.get('size', 0),
                    'file_count': result.get('file_count', 0),
                    'compression_ratio': result.get('compression_ratio', 0),
                    'duration': result.get('duration', 0)
                }
                print(f"BACKUP DEBUG: Final success result: {final_result}")
                return final_result
            else:
                error_result = {
                    'success': False,
                    'error': result.get('error', 'Unknown error during backup')
                }
                print(f"BACKUP DEBUG: Final error result: {error_result}")
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
    
    def _create_tar_backup(self, job: Dict[str, Any], backup_path: str, server: Dict[str, Any]) -> tuple:
        """Create tar.gz backup from job targets."""
        start_time = datetime.now()
        total_size = 0
        file_count = 0
        
        try:
            logger.info(f"Creating tar.gz archive: {backup_path}")
            
            if server['type'] == 'local':
                # Local backup
                return self._create_local_tar_backup(job, backup_path, start_time)
            else:
                # Remote backup via SSH
                return self._create_remote_tar_backup(job, backup_path, server, start_time)
                
        except Exception as e:
            logger.error(f"Tar backup creation failed: {e}")
            return False, {'error': str(e)}
    
    def _create_local_tar_backup(self, job: Dict[str, Any], backup_path: str, start_time: datetime) -> tuple:
        """Create local tar.gz backup."""
        try:
            print("TAR DEBUG: Starting local tar.gz creation")
            print(f"TAR DEBUG: Backup path: {backup_path}")
            print(f"TAR DEBUG: Job targets: {job['targets']}")
            
            total_size = 0
            file_count = 0
            
            # Create tar.gz archive
            print("TAR DEBUG: Opening tar.gz file for writing...")
            with tarfile.open(backup_path, 'w:gz', compresslevel=6) as tar:
                print("TAR DEBUG: Tar file opened successfully")
                
                for i, target in enumerate(job['targets']):
                    print(f"TAR DEBUG: Processing target {i+1}/{len(job['targets'])}: '{target}'")
                    
                    if not target.strip():
                        print("TAR DEBUG: Skipping empty target")
                        continue
                        
                    logger.info(f"Adding to backup: {target}")
                    
                    # Handle different target types
                    if target.startswith('vm:'):
                        print(f"TAR DEBUG: Processing VM target: {target}")
                        vm_name = target[3:]
                        vm_path = f"/var/lib/libvirt/images/{vm_name}"
                        print(f"TAR DEBUG: VM path: {vm_path}")
                        
                        if os.path.exists(vm_path):
                            print(f"TAR DEBUG: VM path exists, adding to archive")
                            tar.add(vm_path, arcname=f"vms/{vm_name}")
                        else:
                            print(f"TAR DEBUG: VM path does not exist: {vm_path}")
                            
                    elif target.startswith('container:'):
                        print(f"TAR DEBUG: Processing container target: {target}")
                        container_name = target[10:]
                        # Export container if Docker is available
                        try:
                            container_export_path = f"/tmp/{container_name}_export.tar"
                            print(f"TAR DEBUG: Exporting container to: {container_export_path}")
                            
                            result = subprocess.run([
                                'docker', 'export', container_name, '-o', container_export_path
                            ], capture_output=True, text=True, check=True)
                            
                            if os.path.exists(container_export_path):
                                print(f"TAR DEBUG: Container export successful, adding to archive")
                                tar.add(container_export_path, arcname=f"containers/{container_name}.tar")
                                os.unlink(container_export_path)
                            else:
                                print(f"TAR DEBUG: Container export file not found")
                                
                        except subprocess.CalledProcessError as e:
                            print(f"TAR DEBUG: Container export failed: {e}")
                            logger.warning(f"Could not export container {container_name}: {e}")
                            
                    else:
                        # Regular file/directory path
                        print(f"TAR DEBUG: Processing regular path: {target}")
                        print(f"TAR DEBUG: Checking if path exists: {os.path.exists(target)}")
                        
                        if os.path.exists(target):
                            print(f"TAR DEBUG: Path exists, calculating size...")
                            
                            # Get size before adding
                            if os.path.isfile(target):
                                size = os.path.getsize(target)
                                total_size += size
                                file_count += 1
                                print(f"TAR DEBUG: File size: {size} bytes")
                                
                            elif os.path.isdir(target):
                                print(f"TAR DEBUG: Directory found, walking files...")
                                dir_file_count = 0
                                dir_size = 0
                                
                                for root, dirs, files in os.walk(target):
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
                                            
                            # Add to archive with relative path
                            arcname = target.lstrip('/') or os.path.basename(target)
                            print(f"TAR DEBUG: Adding to archive as: {arcname}")
                            tar.add(target, arcname=arcname)
                            print(f"TAR DEBUG: Successfully added {target}")
                            
                        else:
                            print(f"TAR DEBUG: Target path does not exist: {target}")
                            logger.warning(f"Target path does not exist: {target}")
            
            print("TAR DEBUG: Tar archive creation completed")
            
            # Get final archive size
            if os.path.exists(backup_path):
                archive_size = os.path.getsize(backup_path)
                print(f"TAR DEBUG: Final archive size: {archive_size} bytes")
            else:
                print("TAR DEBUG ERROR: Archive file does not exist after creation!")
                return False, {'error': 'Archive file not created'}
            
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
                'duration': duration
            }
            
        except Exception as e:
            print(f"TAR DEBUG EXCEPTION: {e}")
            import traceback
            print("TAR DEBUG TRACEBACK:")
            traceback.print_exc()
            
            logger.error(f"Local tar backup failed: {e}")
            # Clean up incomplete archive
            if os.path.exists(backup_path):
                print(f"TAR DEBUG: Cleaning up incomplete archive: {backup_path}")
                os.unlink(backup_path)
            return False, {'error': str(e)}
    
    def _create_remote_tar_backup(self, job: Dict[str, Any], backup_path: str, server: Dict[str, Any], start_time: datetime) -> tuple:
        """Create remote tar.gz backup via SSH."""
        try:
            # Create local temp archive first
            temp_dir = tempfile.mkdtemp()
            temp_archive = os.path.join(temp_dir, os.path.basename(backup_path))
            
            # Create local archive
            success, result = self._create_local_tar_backup(job, temp_archive, start_time)
            
            if not success:
                shutil.rmtree(temp_dir)
                return False, result
            
            # Upload to remote server via SSH
            ssh_success = self._upload_to_remote_server(temp_archive, backup_path, server)
            
            # Clean up temp files
            shutil.rmtree(temp_dir)
            
            if ssh_success:
                return True, result
            else:
                return False, {'error': 'Failed to upload backup to remote server'}
                
        except Exception as e:
            logger.error(f"Remote tar backup failed: {e}")
            return False, {'error': str(e)}
    
    def _upload_to_remote_server(self, local_path: str, remote_path: str, server: Dict[str, Any]) -> bool:
        """Upload backup to remote server via SSH."""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect with authentication
            if server.get('auth_type') == 'ssh_key':
                ssh.connect(
                    hostname=server['host'],
                    port=server.get('port', 22),
                    username=server['username'],
                    key_filename=server.get('ssh_key_path')
                )
            else:
                ssh.connect(
                    hostname=server['host'],
                    port=server.get('port', 22),
                    username=server['username'],
                    password=server.get('password')
                )
            
            # Ensure remote directory exists
            remote_dir = os.path.dirname(remote_path)
            ssh.exec_command(f'mkdir -p {remote_dir}')
            
            # Upload file via SFTP
            sftp = ssh.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            ssh.close()
            
            logger.info(f"Successfully uploaded backup to {server['host']}:{remote_path}")
            return True
            
        except Exception as e:
            logger.error(f"SSH upload failed: {e}")
            return False


# Global backup manager instance
backup_manager = BackupManager()