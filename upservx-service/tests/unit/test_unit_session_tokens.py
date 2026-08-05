"""Tests for signed, expiring, and server-revocable sessions."""

import json
import stat

import pytest

from lib import session_tokens


@pytest.fixture()
def session_store(tmp_path, monkeypatch):
    secret = tmp_path / ".session_secret"
    store = tmp_path / "sessions.json"
    lock = tmp_path / "sessions.lock"
    monkeypatch.delenv("UPSERVX_SESSION_SECRET", raising=False)
    monkeypatch.setattr(session_tokens, "SESSION_SECRET_FILE", str(secret))
    monkeypatch.setattr(session_tokens, "SESSION_STORE_FILE", str(store))
    monkeypatch.setattr(session_tokens, "SESSION_LOCK_FILE", str(lock))
    monkeypatch.setattr(session_tokens, "_SECRET_CACHE", None)
    return secret, store, lock


def test_session_is_signed_persisted_hashed_and_owner_only(session_store):
    secret, store, lock = session_store

    token = session_tokens.create_session_token("alice", ttl_seconds=600)
    persisted = json.loads(store.read_text())

    assert session_tokens.verify_session_token(token) == "alice"
    assert token not in store.read_text()
    assert all(len(key) == 64 for key in persisted)
    for path in (secret, store, lock):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_session_revocation_is_immediate_and_one_session_can_be_preserved(session_store):
    first = session_tokens.create_session_token("alice")
    second = session_tokens.create_session_token("alice")
    other = session_tokens.create_session_token("bob")

    assert session_tokens.revoke_user_sessions("alice", except_token=second) == 1
    assert session_tokens.verify_session_token(first) is None
    assert session_tokens.verify_session_token(second) == "alice"
    assert session_tokens.verify_session_token(other) == "bob"
    assert session_tokens.revoke_session_token(second) is True
    assert session_tokens.verify_session_token(second) is None


def test_tampered_expired_and_unregistered_sessions_fail_closed(
    session_store, monkeypatch
):
    token = session_tokens.create_session_token("alice", ttl_seconds=60)
    issued_at = int(session_tokens.time.time())

    assert session_tokens.verify_session_token(token + "tampered") is None
    monkeypatch.setattr(session_tokens.time, "time", lambda: issued_at + 61)
    assert session_tokens.verify_session_token(token) is None

    monkeypatch.setattr(session_tokens.time, "time", lambda: issued_at)
    fresh = session_tokens.create_session_token("alice")
    session_store[1].write_text("{}")
    assert session_tokens.verify_session_token(fresh) is None


def test_secret_persistence_failure_never_falls_back_to_memory(
    session_store, monkeypatch
):
    def fail_write(*_args, **_kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr(session_tokens, "secure_write_bytes", fail_write)
    with pytest.raises(session_tokens.SessionStoreError, match="unavailable"):
        session_tokens.create_session_token("alice")
    assert session_tokens._SECRET_CACHE is None


def test_corrupt_session_store_fails_closed(session_store):
    session_store[0].write_bytes(b"x" * 48)
    session_store[1].write_text("not-json")

    with pytest.raises(Exception):
        session_tokens.create_session_token("alice")


def test_https_cookie_is_explicit_and_session_is_not_in_response_body(monkeypatch):
    import api.auth as auth

    monkeypatch.setattr(auth, "create_session_token", lambda *_args, **_kwargs: "signed-session")
    response = auth._session_response("alice")
    cookie = response.headers["set-cookie"]

    assert "signed-session" in cookie
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    assert f"Max-Age={auth.SESSION_TTL_SECONDS}" in cookie
    assert "expires=" in cookie.lower()
    assert "session_token" not in json.loads(response.body)


def test_cookie_revocation_uses_the_same_scope_attributes():
    from fastapi.responses import Response
    import api.auth as auth

    response = Response()
    auth._clear_session_cookie(response)
    cookie = response.headers["set-cookie"]

    assert "Max-Age=0" in cookie
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
