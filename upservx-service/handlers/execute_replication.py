#!/usr/bin/env python3
"""
Replication Job Execution Script
This script is called by cron to execute individual replication jobs.
"""

import asyncio
import logging
import os
import sys
import traceback

# Add the service directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
service_dir = os.path.dirname(current_dir)
sys.path.append(service_dir)

from api.cluster import read_replications, execute_replication
from lib.logger import log_system
from handlers.notifications import notify

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/upservx_replication.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def execute_replication_job(replication_id: str) -> bool:
    """Execute a specific replication job by ID."""
    try:
        logger.info(f"Starting replication job execution: {replication_id}")
        log_system(f"Starting scheduled replication job [ID:{replication_id}]")

        replications = read_replications()
        replication = None
        for item in replications:
            if item.get("id") == replication_id:
                replication = item
                break

        if not replication:
            logger.error(f"Replication job {replication_id} not found in configuration")
            log_system(f"Scheduled replication job [ID:{replication_id}] not found", error=True)
            return False

        logger.info(
            "Executing replication job: %s (%s -> %s)",
            replication.get("name", replication_id),
            replication.get("origin_node", "unknown"),
            replication.get("destination_node", "unknown"),
        )

        notify(
            "replication_started",
            f"Replication '{replication.get('name', replication_id)}' started | Type: {replication.get('type', 'unknown')} | From: {replication.get('origin_node', 'unknown')} | To: {replication.get('destination_node', 'unknown')}",
        )

        result = asyncio.run(execute_replication(replication))
        return bool(result)

    except Exception as e:
        logger.error(f"Error executing replication job {replication_id}: {e}")
        logger.error(traceback.format_exc())
        log_system(f"Scheduled replication job [ID:{replication_id}] encountered an error: {e}", error=True)
        return False


def main():
    """Main entry point for cron execution."""
    if len(sys.argv) != 2:
        logger.error("Usage: execute_replication.py <replication_id>")
        sys.exit(1)

    replication_id = sys.argv[1].strip()
    if not replication_id:
        logger.error("Invalid replication ID")
        sys.exit(1)

    success = execute_replication_job(replication_id)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
