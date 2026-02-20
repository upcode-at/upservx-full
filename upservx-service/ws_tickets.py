"""
Short-lived one-time WebSocket authentication tickets.

Browsers cannot attach custom headers or reliably send cookies on cross-origin
WebSocket upgrades.  The expected flow is:

  1. Client calls GET /auth/ws-ticket (normal HTTP, carries the auth cookie).
  2. Server issues a UUID ticket valid for WS_TICKET_TTL_SECONDS seconds.
  3. Client opens the WebSocket with ?token=<ticket> in the URL.
  4. WS handler calls consume_ticket(); on success the ticket is deleted.
"""

import uuid
import threading
from datetime import datetime, timedelta

WS_TICKET_TTL_SECONDS = 30

_tickets: dict = {}          # ticket -> (username, expiry_datetime)
_lock = threading.Lock()


def create_ticket(username: str) -> str:
    """Create and store a new ticket; return the ticket string."""
    ticket = str(uuid.uuid4())
    expiry = datetime.utcnow() + timedelta(seconds=WS_TICKET_TTL_SECONDS)
    with _lock:
        _prune()
        _tickets[ticket] = (username, expiry)
    return ticket


def consume_ticket(ticket: str) -> str | None:
    """Validate and delete a ticket.  Returns username on success, None on failure."""
    with _lock:
        entry = _tickets.pop(ticket, None)
    if entry is None:
        return None
    username, expiry = entry
    if datetime.utcnow() > expiry:
        return None
    return username


def _prune():
    """Remove expired tickets (call while holding _lock)."""
    now = datetime.utcnow()
    expired = [k for k, (_, exp) in _tickets.items() if exp < now]
    for k in expired:
        del _tickets[k]
