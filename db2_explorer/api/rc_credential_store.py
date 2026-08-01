"""In-memory Row Compare credential cache keyed by browser ``rc_sid``."""

from __future__ import annotations

from typing import Any

_STORE: dict[str, dict[str, Any]] = {}


def save_connect_payload(rc_sid: str, payload: dict[str, Any]) -> None:
    sid = (rc_sid or "").strip()
    if not sid:
        raise ValueError("rc_sid is required.")
    _STORE[sid] = dict(payload)


def get_connect_payload(rc_sid: str) -> dict[str, Any] | None:
    sid = (rc_sid or "").strip()
    if not sid:
        return None
    stored = _STORE.get(sid)
    return dict(stored) if stored is not None else None


def clear_connect_payload(rc_sid: str) -> None:
    sid = (rc_sid or "").strip()
    if sid:
        _STORE.pop(sid, None)
