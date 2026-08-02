"""In-memory Schema Compare credential cache keyed by browser ``sch_sid`` + ``sch_token``."""

from __future__ import annotations

import os
import secrets
import time
from typing import Any

_DEFAULT_TTL_SECONDS = 30 * 60
_BIND_TTL_SECONDS = 120

_STORE: dict[str, dict[str, Any]] = {}
_BIND_STORE: dict[str, dict[str, Any]] = {}


def _ttl_seconds() -> int:
    raw = os.getenv("SCH_CREDENTIAL_TTL_SECONDS", os.getenv("RC_CREDENTIAL_TTL_SECONDS", str(_DEFAULT_TTL_SECONDS)))
    try:
        return max(60, int(raw))
    except ValueError:
        return _DEFAULT_TTL_SECONDS


def _now() -> float:
    return time.time()


def purge_expired() -> None:
    """Drop expired credential and bind entries."""
    now = _now()
    for sid in list(_STORE):
        if float(_STORE[sid].get("expires_at", 0)) <= now:
            _STORE.pop(sid, None)
    for bind_id in list(_BIND_STORE):
        if float(_BIND_STORE[bind_id].get("expires_at", 0)) <= now:
            _BIND_STORE.pop(bind_id, None)


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def save_connect_payload(sch_sid: str, payload: dict[str, Any]) -> str:
    """Persist credentials; return a fresh ``sch_token`` for API / session use."""
    sid = (sch_sid or "").strip()
    if not sid:
        raise ValueError("sch_sid is required.")

    purge_expired()
    token = _new_token()
    now = _now()
    _STORE[sid] = {
        "token": token,
        "payload": dict(payload),
        "expires_at": now + _ttl_seconds(),
        "updated_at": now,
    }
    return token


def _token_matches(stored: str, provided: str) -> bool:
    if not stored or not provided:
        return False
    return secrets.compare_digest(stored, provided.strip())


def has_connect_session(sch_sid: str) -> bool:
    sid = (sch_sid or "").strip()
    if not sid:
        return False
    purge_expired()
    entry = _STORE.get(sid)
    if entry is None:
        return False
    if float(entry.get("expires_at", 0)) <= _now():
        _STORE.pop(sid, None)
        return False
    return True


def verify_connect_token(sch_sid: str, sch_token: str) -> bool:
    sid = (sch_sid or "").strip()
    if not sid:
        return False
    purge_expired()
    entry = _STORE.get(sid)
    if entry is None:
        return False
    if float(entry.get("expires_at", 0)) <= _now():
        _STORE.pop(sid, None)
        return False
    return _token_matches(str(entry.get("token", "")), sch_token)


def get_connect_payload(sch_sid: str, sch_token: str = "") -> dict[str, Any] | None:
    """Return credential payload when ``sch_token`` matches."""
    sid = (sch_sid or "").strip()
    if not sid:
        return None

    purge_expired()
    entry = _STORE.get(sid)
    if entry is None:
        return None

    if float(entry.get("expires_at", 0)) <= _now():
        _STORE.pop(sid, None)
        return None

    stored_token = str(entry.get("token", ""))
    if not sch_token or not _token_matches(stored_token, sch_token):
        return None

    entry["expires_at"] = _now() + _ttl_seconds()
    return dict(entry.get("payload") or {})


def get_connect_token(sch_sid: str) -> str | None:
    """Return the current token for a session (Streamlit session_state sync only)."""
    sid = (sch_sid or "").strip()
    if not sid:
        return None
    purge_expired()
    entry = _STORE.get(sid)
    if entry is None or float(entry.get("expires_at", 0)) <= _now():
        return None
    return str(entry.get("token", "")) or None


def clear_connect_payload(sch_sid: str) -> None:
    sid = (sch_sid or "").strip()
    if sid:
        _STORE.pop(sid, None)


def create_bind_token(sch_sid: str, sch_token: str) -> str:
    """One-time URL token so Streamlit can bind ``sch_sid`` without putting it in the URL."""
    sid = (sch_sid or "").strip()
    token = (sch_token or "").strip()
    if not sid or not token:
        raise ValueError("sch_sid and sch_token are required.")

    purge_expired()
    bind_id = secrets.token_urlsafe(24)
    _BIND_STORE[bind_id] = {
        "sch_sid": sid,
        "sch_token": token,
        "expires_at": _now() + _BIND_TTL_SECONDS,
    }
    return bind_id


def consume_bind_token(bind_id: str) -> tuple[str, str] | None:
    """Exchange a one-time bind token for ``(sch_sid, sch_token)``."""
    key = (bind_id or "").strip()
    if not key:
        return None

    purge_expired()
    entry = _BIND_STORE.pop(key, None)
    if entry is None:
        return None
    if float(entry.get("expires_at", 0)) <= _now():
        return None

    sid = str(entry.get("sch_sid", "")).strip()
    token = str(entry.get("sch_token", "")).strip()
    if not sid or not token:
        return None
    return sid, token
