"""Log viewing routes."""

from fastapi import APIRouter, HTTPException, Query

from lib.logger import ACTIVITY_LOG_FILE
from handlers.settings import get_log_files, read_log_file

router = APIRouter()


@router.get("/logs")
def api_list_logs():
    """List available log files."""
    return {"logs": get_log_files()}


@router.get("/logs/activity")
def api_activity_log(lines: int = Query(100, ge=0)):
    """Read the UpservX activity log from /var/log/upservx/activity.log."""
    try:
        content = read_log_file(ACTIVITY_LOG_FILE, lines=lines)
        return {
            "name": "upservx/activity.log",
            "path": ACTIVITY_LOG_FILE,
            "content": content,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/activity-log")
def api_activity_log_legacy(lines: int = Query(100, ge=0)):
    """Backward-compatible alias for the activity log endpoint."""
    return api_activity_log(lines=lines)


@router.get("/logs/{name:path}")
def api_read_log(name: str, lines: int = Query(100, ge=0)):
    """Read a system log file."""
    try:
        content = read_log_file(name, lines=lines)
        return {"name": name, "content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
