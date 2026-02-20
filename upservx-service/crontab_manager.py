"""
Crontab Management for Backup Jobs
Manages automatic scheduling of backup jobs in system crontab
"""

import os
import re
import subprocess
import tempfile
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class CrontabManager:
    """Manages crontab entries for backup jobs."""
    
    BACKUP_JOB_MARKER = "# UPSERVX_BACKUP_JOB"
    BACKUP_SECTION_START = "# === UPSERVX BACKUP JOBS START ==="
    BACKUP_SECTION_END = "# === UPSERVX BACKUP JOBS END ==="

    # Each cron field: digits, *, , - /  only — no spaces, semicolons, or shell chars
    _CRON_FIELD_RE = re.compile(r'^[0-9*,\-/]+$')
    # Allowed ranges per field position (min, max) — * and step/range also valid
    _CRON_FIELD_RANGES = [
        (0, 59),   # minute
        (0, 23),   # hour
        (1, 31),   # day-of-month
        (1, 12),   # month
        (0, 7),    # day-of-week (0 and 7 both = Sunday)
    ]
    _CRON_FIELD_NAMES = ["minute", "hour", "day-of-month", "month", "day-of-week"]

    @classmethod
    def _validate_cron_field(cls, value: str, field_name: str) -> None:
        """Raise ValueError if a cron field contains invalid characters."""
        if not cls._CRON_FIELD_RE.match(value):
            raise ValueError(
                f"Invalid cron {field_name} field {value!r}: "
                "only digits, *, , - / are allowed"
            )

    @classmethod
    def _validate_schedule(cls, schedule: str) -> list[str]:
        """Parse and validate a 5-field cron schedule string.  Returns the five fields."""
        parts = schedule.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Cron schedule must have exactly 5 fields, got: {schedule!r}")
        for part, name in zip(parts, cls._CRON_FIELD_NAMES):
            cls._validate_cron_field(part, name)
        return parts

    @staticmethod
    def _sanitize_job_name(name: str) -> str:
        """Strip characters that could break cron lines or inject shell commands."""
        # Remove newlines, carriage returns, null bytes
        sanitized = re.sub(r'[\r\n\x00]', '', name)
        # Remove shell-significant characters that have no place in a comment
        sanitized = re.sub(r'[;|&`$<>()\\\'"!]', '', sanitized)
        return sanitized[:128]  # hard cap to prevent oversized lines
    
    def __init__(self):
        self.crontab_path = "/etc/crontab"
        self.python_executable = "/usr/bin/python3"
        # Use dynamic path based on current script location
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.backup_script_path = os.path.join(current_dir, "execute_backup.py")
    
    def read_crontab(self) -> List[str]:
        """Read current crontab content."""
        try:
            if os.path.exists(self.crontab_path):
                with open(self.crontab_path, 'r') as f:
                    return f.readlines()
            return []
        except Exception as e:
            logger.error(f"Error reading crontab: {e}")
            return []
    
    def write_crontab(self, lines: List[str]) -> bool:
        """Write lines to crontab."""
        try:
            # Write to temporary file first
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.crontab') as temp_file:
                temp_file.writelines(lines)
                temp_path = temp_file.name
            
            # Copy to actual crontab location with sudo
            result = subprocess.run([
                'sudo', 'cp', temp_path, self.crontab_path
            ], capture_output=True, text=True)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            if result.returncode != 0:
                logger.error(f"Error writing crontab: {result.stderr}")
                return False
            
            # Restart cron service to reload
            subprocess.run(['sudo', 'systemctl', 'reload', 'cron'], capture_output=True)
            
            return True
        except Exception as e:
            logger.error(f"Error writing crontab: {e}")
            return False
    
    def ensure_backup_section(self, lines: List[str]) -> List[str]:
        """Ensure backup section markers exist in crontab."""
        # Check if section already exists
        has_start = any(self.BACKUP_SECTION_START in line for line in lines)
        has_end = any(self.BACKUP_SECTION_END in line for line in lines)
        
        if has_start and has_end:
            return lines
        
        # Add section markers at the end
        if not lines or not lines[-1].endswith('\n'):
            lines.append('\n')
        
        lines.extend([
            f"\n{self.BACKUP_SECTION_START}\n",
            f"{self.BACKUP_SECTION_END}\n"
        ])
        
        return lines
    
    def get_backup_job_cron_entry(self, job_id: int, schedule: str, job_name: str) -> str:
        """Generate cron entry for a backup job."""
        # Validate and parse the schedule — raises ValueError on bad input
        minute, hour, day, month, weekday = self._validate_schedule(schedule)

        # Sanitize the job name so it cannot inject extra cron fields or shell commands
        safe_name = self._sanitize_job_name(job_name)

        # Build cron entry with user specification for /etc/crontab
        user = "root"  # Run backups as root for system access
        command = f"{self.python_executable} {self.backup_script_path} {job_id}"

        cron_entry = f"{minute} {hour} {day} {month} {weekday} {user} {command} {self.BACKUP_JOB_MARKER}_ID_{job_id} # {safe_name}\n"

        return cron_entry
    
    def add_backup_job(self, job_id: int, schedule: str, job_name: str) -> bool:
        """Add backup job to crontab."""
        try:
            lines = self.read_crontab()
            lines = self.ensure_backup_section(lines)
            
            # Remove existing entry for this job if it exists
            self.remove_backup_job(job_id, write_immediately=False)
            lines = self.read_crontab()  # Re-read after removal
            
            # Find insertion point (before section end marker)
            insert_index = -1
            for i, line in enumerate(lines):
                if self.BACKUP_SECTION_END in line:
                    insert_index = i
                    break
            
            if insert_index == -1:
                lines = self.ensure_backup_section(lines)
                for i, line in enumerate(lines):
                    if self.BACKUP_SECTION_END in line:
                        insert_index = i
                        break
            
            # Generate and insert cron entry
            cron_entry = self.get_backup_job_cron_entry(job_id, schedule, job_name)
            lines.insert(insert_index, cron_entry)
            
            # Write updated crontab
            return self.write_crontab(lines)
            
        except Exception as e:
            logger.error(f"Error adding backup job {job_id} to crontab: {e}")
            return False
    
    def remove_backup_job(self, job_id: int, write_immediately: bool = True) -> bool:
        """Remove backup job from crontab."""
        try:
            lines = self.read_crontab()
            
            # Filter out lines for this job
            marker = f"{self.BACKUP_JOB_MARKER}_ID_{job_id}"
            filtered_lines = [line for line in lines if marker not in line]
            
            if len(filtered_lines) != len(lines):
                if write_immediately:
                    return self.write_crontab(filtered_lines)
                else:
                    # Just update the file for the caller to write later
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.crontab') as temp_file:
                        temp_file.writelines(filtered_lines)
                        temp_path = temp_file.name
                    subprocess.run(['sudo', 'cp', temp_path, self.crontab_path], capture_output=True)
                    os.unlink(temp_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing backup job {job_id} from crontab: {e}")
            return False
    
    def list_backup_jobs(self) -> List[dict]:
        """List all backup jobs currently in crontab."""
        try:
            lines = self.read_crontab()
            backup_jobs = []
            
            for line in lines:
                if self.BACKUP_JOB_MARKER in line and "_ID_" in line:
                    # Extract job ID from marker
                    try:
                        marker_start = line.find(f"{self.BACKUP_JOB_MARKER}_ID_")
                        if marker_start != -1:
                            id_start = marker_start + len(f"{self.BACKUP_JOB_MARKER}_ID_")
                            id_end = line.find(" ", id_start)
                            if id_end == -1:
                                id_end = line.find("#", id_start)
                            if id_end == -1:
                                id_end = len(line.strip())
                            
                            job_id = int(line[id_start:id_end])
                            
                            # Extract schedule and name
                            parts = line.strip().split()
                            if len(parts) >= 8:
                                schedule = " ".join(parts[:5])
                                comment_start = line.find("#")
                                job_name = line[comment_start+1:].strip() if comment_start != -1 else f"Job {job_id}"
                                
                                backup_jobs.append({
                                    "job_id": job_id,
                                    "schedule": schedule,
                                    "name": job_name,
                                    "cron_line": line.strip()
                                })
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Could not parse backup job line: {line.strip()} - {e}")
                        continue
            
            return backup_jobs
            
        except Exception as e:
            logger.error(f"Error listing backup jobs: {e}")
            return []

# Global instance
crontab_manager = CrontabManager()