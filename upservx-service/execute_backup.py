#!/usr/bin/env python3
"""
Backup Job Execution Script
This script is called by cron to execute individual backup jobs.
"""

import sys
import os
import logging
import json
from datetime import datetime
import traceback

# Add the service directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from backup_db import backup_db
from backup import BackupManager
from upservx_logger import log_backup
from notifications import notify

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/upservx_backup.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def execute_backup_job(job_id: int) -> bool:
    """Execute a specific backup job by ID."""
    try:
        logger.info(f"Starting backup job execution: {job_id}")
        log_backup(f"Starting scheduled backup job [ID:{job_id}]")
        
        # Get job details from database
        job = backup_db.get_backup_job(job_id)
        if not job:
            logger.error(f"Backup job {job_id} not found in database")
            log_backup(f"Scheduled backup job [ID:{job_id}] not found in database", error=True)
            return False
        
        logger.info(f"Executing backup job: {job['name']}")
        
        # Get server details
        server = backup_db.get_backup_server(job['server_id'])
        if not server:
            logger.error(f"Backup server {job['server_id']} not found for job {job_id}")
            return False
        
        # Create backup manager and execute
        backup_manager = BackupManager()
        
        # Create backup instance record
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        instance_data = {
            'job_id': job_id,
            'server_id': server['id'],
            'backup_name': f"{job['name']}_{timestamp}",
            'backup_path': '',  # Will be updated after backup creation
            'backup_size': 0,
            'status': 'in_progress',
            'backup_type': job['backup_type'],
            'targets': json.dumps(job['targets']),
            'error_message': None,
            'started': datetime.now().isoformat(),
            'completed': None
        }
        
        instance_id = backup_db.create_backup_instance(instance_data)
        
        try:
            # Execute the actual backup
            result = backup_manager.execute_backup(job, server)
            
            # Update instance with results
            if result.get('success', False):
                backup_db.update_backup_instance(instance_id, {
                    'status': 'completed',
                    'completed': datetime.now().isoformat(),
                    'backup_size': result.get('size', 0),
                    'backup_path': result.get('backup_path', ''),
                    'error_message': None
                })
                logger.info(f"Backup job {job_id} completed successfully")
                log_backup(f"Scheduled backup job [{job['name']}] (ID:{job_id}) completed successfully")
                size_mb = round(result.get('size', 0) / 1024 / 1024, 2)
                notify("backup_success", f"Backup job '{job['name']}' completed | Size: {size_mb} MB | Path: {result.get('backup_path', 'n/a')}")
                return True
            else:
                backup_db.update_backup_instance(instance_id, {
                    'status': 'failed',
                    'completed': datetime.now().isoformat(),
                    'error_message': result.get('error', 'Unknown error')
                })
                logger.error(f"Backup job {job_id} failed: {result.get('error')}")
                log_backup(f"Scheduled backup job [{job['name']}] (ID:{job_id}) failed: {result.get('error')}", error=True)
                notify("backup_failure", f"Backup job '{job['name']}' FAILED | Error: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            # Update instance with error
            backup_db.update_backup_instance(instance_id, {
                'status': 'failed',
                'completed': datetime.now().isoformat(),
                'error_message': str(e)
            })
            raise
        
    except Exception as e:
        logger.error(f"Error executing backup job {job_id}: {e}")
        logger.error(traceback.format_exc())
        log_backup(f"Scheduled backup job [ID:{job_id}] encountered an error: {e}", error=True)
        return False

def main():
    """Main entry point for cron execution."""
    if len(sys.argv) != 2:
        logger.error("Usage: execute_backup.py <job_id>")
        sys.exit(1)
    
    try:
        job_id = int(sys.argv[1])
    except ValueError:
        logger.error(f"Invalid job ID: {sys.argv[1]}")
        sys.exit(1)
    
    success = execute_backup_job(job_id)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()