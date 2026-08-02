"""In-memory Row Compare result cache — survives iframe rerenders (Edit → Back)."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from db2_explorer.api.rc_credential_store import (
    get_connect_payload,
    has_connect_session,
    purge_expired,
)

_DEFAULT_TTL_SECONDS = 30 * 60

_RESULT_STORE: dict[str, dict[str, Any]] = {}

_CREDENTIAL_KEYS = (
    "cmp_db2_database",
    "cmp_db2_host",
    "cmp_db2_port",
    "cmp_db2_user",
    "cmp_db2_password",
    "cmp_az_server",
    "cmp_az_database",
    "cmp_az_auth",
    "cmp_az_trust_cert",
)


def _ttl_seconds() -> int:
    raw = os.getenv("RC_CREDENTIAL_TTL_SECONDS", str(_DEFAULT_TTL_SECONDS))
    try:
        return max(60, int(raw))
    except ValueError:
        return _DEFAULT_TTL_SECONDS


def _now() -> float:
    return time.time()


def credentials_payload_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Build a credential dict from Streamlit ``session_state`` keys."""
    return {
        "cmp_db2_database": str(session.get("cmp_db2_database", "")).strip(),
        "cmp_db2_host": str(session.get("cmp_db2_host", "")).strip(),
        "cmp_db2_port": int(session.get("cmp_db2_port", 50000)),
        "cmp_db2_user": str(session.get("cmp_db2_user", "")).strip(),
        "cmp_db2_password": str(session.get("cmp_db2_password", "")),
        "cmp_az_server": str(session.get("cmp_az_server", "")).strip(),
        "cmp_az_database": str(session.get("cmp_az_database", "")).strip(),
        "cmp_az_auth": str(session.get("cmp_az_auth", "entra")).strip(),
        "cmp_az_trust_cert": bool(session.get("cmp_az_trust_cert", True)),
    }


def connection_fingerprint(payload: dict[str, Any]) -> str:
    """Stable hash of connection fields — used to invalidate stale comparison results."""
    data = {key: payload.get(key) for key in _CREDENTIAL_KEYS}
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _purge_stale_results() -> None:
    purge_expired()
    now = _now()
    for sid in list(_RESULT_STORE):
        entry = _RESULT_STORE[sid]
        if float(entry.get("expires_at", 0)) <= now or not has_connect_session(sid):
            _RESULT_STORE.pop(sid, None)


def save_result_snapshot(
    rc_sid: str,
    credentials: dict[str, Any],
    *,
    metrics: dict[str, Any],
    tbody_views: dict[str, str],
    tbody_html: str,
    target_table_mode: str,
    table_count: int,
) -> None:
    sid = (rc_sid or "").strip()
    if not sid:
        return
    _purge_stale_results()
    now = _now()
    _RESULT_STORE[sid] = {
        "fingerprint": connection_fingerprint(credentials),
        "metrics": dict(metrics),
        "tbody_views": dict(tbody_views),
        "tbody_html": tbody_html,
        "target_table_mode": target_table_mode,
        "table_count": table_count,
        "expires_at": now + _ttl_seconds(),
        "updated_at": now,
    }


def get_result_snapshot_for_session(
    rc_sid: str,
    rc_token: str,
) -> dict[str, Any] | None:
    """Look up cached results using credentials from the server store (avoids session drift)."""
    sid = (rc_sid or "").strip()
    token = (rc_token or "").strip()
    if not sid or not token:
        return None
    payload = get_connect_payload(sid, token)
    if not payload:
        return None
    return get_result_snapshot(sid, payload)


def get_result_snapshot(rc_sid: str, credentials: dict[str, Any]) -> dict[str, Any] | None:
    sid = (rc_sid or "").strip()
    if not sid:
        return None
    _purge_stale_results()
    entry = _RESULT_STORE.get(sid)
    if entry is None:
        return None
    if float(entry.get("expires_at", 0)) <= _now():
        _RESULT_STORE.pop(sid, None)
        return None
    if entry.get("fingerprint") != connection_fingerprint(credentials):
        return None
    entry["expires_at"] = _now() + _ttl_seconds()
    return dict(entry)


def clear_result_snapshot(rc_sid: str) -> None:
    sid = (rc_sid or "").strip()
    if sid:
        _RESULT_STORE.pop(sid, None)


def invalidate_if_credentials_changed(
    rc_sid: str,
    old_credentials: dict[str, Any] | None,
    new_credentials: dict[str, Any],
) -> bool:
    """Clear cached results when connection fields change. Returns True if cleared."""
    old_fp = connection_fingerprint(old_credentials) if old_credentials else None
    new_fp = connection_fingerprint(new_credentials)
    if old_fp != new_fp:
        clear_result_snapshot(rc_sid)
        return True
    return False
