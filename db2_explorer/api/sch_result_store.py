"""In-memory Schema Compare result cache — survives Edit → Back navigation."""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from db2_explorer.api.sch_credential_store import get_connect_payload, has_connect_session, purge_expired

_DEFAULT_TTL_SECONDS = 30 * 60

_RESULT_STORE: dict[str, dict[str, Any]] = {}

_CREDENTIAL_KEYS = (
    "sch_gitlab_token",
    "sch_branch",
    "sch_database",
    "sch_server",
    "sch_az_server",
    "sch_az_database",
    "sch_az_auth",
    "sch_az_trust_cert",
)


def _ttl_seconds() -> int:
    raw = os.getenv("SCH_CREDENTIAL_TTL_SECONDS", os.getenv("RC_CREDENTIAL_TTL_SECONDS", str(_DEFAULT_TTL_SECONDS)))
    try:
        return max(60, int(raw))
    except ValueError:
        return _DEFAULT_TTL_SECONDS


def _now() -> float:
    return time.time()


def credentials_payload_from_session(session: dict[str, Any]) -> dict[str, Any]:
    """Build a credential dict from Streamlit ``session_state`` keys."""
    return {
        "sch_gitlab_token": str(session.get("sch_gitlab_token", "")),
        "sch_branch": str(session.get("sch_branch", "main")).strip(),
        "sch_database": str(session.get("sch_database", "")).strip(),
        "sch_server": str(session.get("sch_server", "")).strip(),
        "sch_az_server": str(session.get("sch_az_server", "")).strip(),
        "sch_az_database": str(session.get("sch_az_database", "")).strip(),
        "sch_az_auth": str(session.get("sch_az_auth", "entra")).strip(),
        "sch_az_trust_cert": bool(session.get("sch_az_trust_cert", True)),
    }


def connection_fingerprint(payload: dict[str, Any]) -> str:
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
    sch_sid: str,
    credentials: dict[str, Any],
    *,
    summary: dict[str, int],
    table_html: str,
    objects: dict[str, dict[str, Any]],
    source_label: str,
    target_label: str,
    bundle_path: str,
    selected_object_key: str = "",
) -> None:
    sid = (sch_sid or "").strip()
    if not sid:
        return
    _purge_stale_results()
    now = _now()
    _RESULT_STORE[sid] = {
        "fingerprint": connection_fingerprint(credentials),
        "summary": dict(summary),
        "table_html": table_html,
        "objects": dict(objects),
        "source_label": source_label,
        "target_label": target_label,
        "bundle_path": bundle_path,
        "selected_object_key": selected_object_key,
        "expires_at": now + _ttl_seconds(),
        "updated_at": now,
    }


def get_result_snapshot(sch_sid: str, credentials: dict[str, Any]) -> dict[str, Any] | None:
    sid = (sch_sid or "").strip()
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


def get_result_snapshot_for_session(
    sch_sid: str,
    sch_token: str,
) -> dict[str, Any] | None:
    sid = (sch_sid or "").strip()
    token = (sch_token or "").strip()
    if not sid or not token:
        return None
    payload = get_connect_payload(sid, token)
    if not payload:
        return None
    return get_result_snapshot(sid, payload)


def clear_result_snapshot(sch_sid: str) -> None:
    sid = (sch_sid or "").strip()
    if sid:
        _RESULT_STORE.pop(sid, None)


def invalidate_if_credentials_changed(
    sch_sid: str,
    old_credentials: dict[str, Any] | None,
    new_credentials: dict[str, Any],
) -> bool:
    old_fp = connection_fingerprint(old_credentials) if old_credentials else None
    new_fp = connection_fingerprint(new_credentials)
    if old_fp != new_fp:
        clear_result_snapshot(sch_sid)
        return True
    return False
