"""Log viewing routes."""

from fastapi import APIRouter, HTTPException

from lib.logger import ACTIVITY_LOG_FILE
from handlers.settings import get_log_files, read_log_file

router = APIRouter()


@router.get("/logs")
def api_list_logs():
    """List available log files."""
    return {"logs": get_log_files()}


@router.get("/logs/{name}")
def api_read_log(name: str):
    """Read a system log file."""
    try:
        content = read_log_file(name)
        return {"name": name, "content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/activity-log")
def api_activity_log():
    """Read the UpservX activity / audit log."""
    try:
        content = read_log_file(ACTIVITY_LOG_FILE)
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
