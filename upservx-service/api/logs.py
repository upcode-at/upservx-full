"""Log viewing routes."""

from fastapi import APIRouter, HTTPException, Query, Response

from lib.logger import ACTIVITY_LOG_FILE
from handlers.settings import get_log_files, read_log_file

router = APIRouter()


@router.get("/logs")
def api_list_logs():
    """List available log files."""
    return {"logs": get_log_files()}


@router.get("/logs/activity")
def api_activity_log(
    lines: int = Query(100, ge=0),
    fmt: str = Query("text", alias="format", pattern="^(text|json)$"),
):
    """Read the UpservX activity log from /var/log/upservx/activity.log."""
    try:
        content = read_log_file(ACTIVITY_LOG_FILE, lines=lines)
        if fmt == "json":
            return {
                "name": "upservx/activity.log",
                "path": ACTIVITY_LOG_FILE,
                "content": content,
            }
        return Response(content=content, media_type="text/plain; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/activity-log")
def api_activity_log_legacy(
    lines: int = Query(100, ge=0),
    fmt: str = Query("text", alias="format", pattern="^(text|json)$"),
):
    """Backward-compatible alias for the activity log endpoint."""
    return api_activity_log(lines=lines, fmt=fmt)


@router.get("/logs/{name:path}")
def api_read_log(
    name: str,
    lines: int = Query(100, ge=0),
    fmt: str = Query("text", alias="format", pattern="^(text|json)$"),
):
    """Read a system log file."""
    try:
        content = read_log_file(name, lines=lines)
        if fmt == "json":
            return {"name": name, "content": content}
        return Response(content=content, media_type="text/plain; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
