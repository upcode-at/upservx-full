#!/usr/bin/env python3
"""
Backup Job Execution Script
This script is called by cron to execute individual backup jobs.
"""

import sys
import os
import logging

# Add the service directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
service_dir = os.path.dirname(current_dir)
sys.path.insert(0, service_dir)

from lib.backup_execution import queue_backup_job
from lib.logger import log_backup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

def execute_backup_job(job_id: int) -> bool:
    """Queue a scheduled backup for the persistent worker."""
    try:
        persistent_job = queue_backup_job(job_id)
        logger.info("Queued backup job %s as %s", job_id, persistent_job["id"])
        log_backup(f"Queued scheduled backup job [ID:{job_id}]")
        return True
    except Exception as e:
        logger.exception("Error queueing backup job %s: %s", job_id, e)
        log_backup(f"Scheduled backup job [ID:{job_id}] could not be queued: {e}", error=True)
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
