"""
Unit-Tests für lib/ws_tickets.py
==================================
Testet Ticket-Erstellung, -Verbrauch, Ablauf und Thread-Sicherheit.
Kein Netzwerkzugriff oder Dateisystem nötig.
"""

import time
import threading
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

# Modul frisch importieren – interne Zustände (_tickets dict) zurücksetzen
import importlib
import lib.ws_tickets as ws_tickets_mod


def _reset_tickets():
    """Hilfsfunktion: leert den internen Ticket-Speicher zwischen Tests."""
    with ws_tickets_mod._lock:
        ws_tickets_mod._tickets.clear()


# ---------------------------------------------------------------------------
# create_ticket
# ---------------------------------------------------------------------------

class TestCreateTicket:
    def setup_method(self):
        _reset_tickets()

    def test_returns_string(self):
        ticket = ws_tickets_mod.create_ticket("alice")
        assert isinstance(ticket, str)

    def test_ticket_is_uuid_format(self):
        import uuid
        ticket = ws_tickets_mod.create_ticket("alice")
        # Sollte als UUID parsebar sein
        uuid.UUID(ticket)

    def test_tickets_are_unique(self):
        t1 = ws_tickets_mod.create_ticket("alice")
        t2 = ws_tickets_mod.create_ticket("alice")
        assert t1 != t2

    def test_ticket_stored_internally(self):
        ticket = ws_tickets_mod.create_ticket("bob")
        assert ticket in ws_tickets_mod._tickets

    def test_raises_when_store_full(self):
        # MAX_LIVE_TICKETS temporär auf 0 setzen
        with patch.object(ws_tickets_mod, "_MAX_LIVE_TICKETS", 0):
            _reset_tickets()
            with pytest.raises(RuntimeError, match="ticket store full"):
                ws_tickets_mod.create_ticket("alice")


# ---------------------------------------------------------------------------
# consume_ticket
# ---------------------------------------------------------------------------

class TestConsumeTicket:
    def setup_method(self):
        _reset_tickets()

    def test_returns_username_on_valid_ticket(self):
        ticket = ws_tickets_mod.create_ticket("carol")
        assert ws_tickets_mod.consume_ticket(ticket) == "carol"

    def test_ticket_deleted_after_consumption(self):
        ticket = ws_tickets_mod.create_ticket("carol")
        ws_tickets_mod.consume_ticket(ticket)
        assert ticket not in ws_tickets_mod._tickets

    def test_returns_none_for_unknown_ticket(self):
        assert ws_tickets_mod.consume_ticket("not-a-real-ticket") is None

    def test_returns_none_for_double_consumption(self):
        ticket = ws_tickets_mod.create_ticket("dave")
        ws_tickets_mod.consume_ticket(ticket)
        # Zweiter Aufruf – Ticket bereits verbraucht
        assert ws_tickets_mod.consume_ticket(ticket) is None

    def test_returns_none_for_expired_ticket(self):
        ticket = ws_tickets_mod.create_ticket("eve")
        # Ablaufzeit in die Vergangenheit setzen
        with ws_tickets_mod._lock:
            username, _ = ws_tickets_mod._tickets[ticket]
            ws_tickets_mod._tickets[ticket] = (username, datetime.utcnow() - timedelta(seconds=1))
        assert ws_tickets_mod.consume_ticket(ticket) is None


# ---------------------------------------------------------------------------
# Thread-Sicherheit
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def setup_method(self):
        _reset_tickets()

    def test_concurrent_create_and_consume(self):
        """Mehrere Threads erstellen und verbrauchen parallel Tickets – kein Deadlock."""
        results = []
        errors = []

        def worker(username: str):
            try:
                ticket = ws_tickets_mod.create_ticket(username)
                user = ws_tickets_mod.consume_ticket(ticket)
                results.append(user)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(f"user{i}",)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 50
        assert all(r is not None for r in results)


# ---------------------------------------------------------------------------
# Pruning abgelaufener Tickets
# ---------------------------------------------------------------------------

class TestPruning:
    def setup_method(self):
        _reset_tickets()

    def test_prune_removes_expired_entries(self):
        ticket = ws_tickets_mod.create_ticket("frank")
        # Ticket manuell ablaufen lassen
        with ws_tickets_mod._lock:
            username, _ = ws_tickets_mod._tickets[ticket]
            ws_tickets_mod._tickets[ticket] = (username, datetime.utcnow() - timedelta(seconds=1))

        # Neues Ticket erstellen löst _prune() aus
        ws_tickets_mod.create_ticket("grace")
        assert ticket not in ws_tickets_mod._tickets
