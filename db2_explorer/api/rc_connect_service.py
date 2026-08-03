"""Row Compare connection test helpers for the background API server."""

from __future__ import annotations

from typing import Any

from db2_explorer.api.rc_credential_store import (
    create_bind_token,
    get_connect_payload,
    has_connect_session,
    save_connect_payload,
    verify_connect_token,
)
from db2_explorer.api.rc_result_store import invalidate_if_credentials_changed
from db2_explorer.clients.azure import AUTH_METHOD_LABELS, AzureConnection, query as azure_query, test_connection as test_azure
from db2_explorer.clients.db2 import query_single
from db2_explorer.data.connections import Connection

_AZ_AUTH_MAP = {
    "entra": "azure_ad_interactive",
    "azure_ad_interactive": "azure_ad_interactive",
    "windows": "windows_integrated",
    "windows_integrated": "windows_integrated",
}


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def test_db2_json(body: dict[str, Any]) -> dict[str, Any]:
    database = str(body.get("database", "")).strip()
    host = str(body.get("host", "")).strip()
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    port = _parse_int(body.get("port"), 50000)

    if not all([database, host, username, password]):
        return {"ok": False, "error": "Database, Host, Username, and Password are required."}

    target = f"{username}@{host}:{port}/{database}"
    conn = Connection(dbname=database, host=host, port=port)
    out = query_single(conn, username, password, "SELECT 1 AS OK FROM SYSIBM.SYSDUMMY1")
    if out.ok:
        return {"ok": True, "message": f"DB2 connection OK ({target})."}
    err = out.error or "DB2 connection failed."
    return {"ok": False, "error": f"{err} — tried {target}."}


def test_azure_json(body: dict[str, Any]) -> dict[str, Any]:
    server = str(body.get("server", "")).strip()
    database = str(body.get("database", "")).strip()
    auth_raw = str(body.get("auth_method", "entra")).strip().lower()
    auth_method = _AZ_AUTH_MAP.get(auth_raw, "azure_ad_interactive")
    trust = bool(body.get("trust_server_certificate", False))

    if not all([server, database]):
        return {"ok": False, "error": "Server and Database are required."}

    az_conn = AzureConnection(
        server=server,
        database=database,
        auth_method=auth_method,
        trust_server_certificate=trust,
    )
    out = test_azure(az_conn)
    if out.ok:
        label = AUTH_METHOD_LABELS.get(auth_method, auth_method)
        return {"ok": True, "message": f"Target connection OK ({label})."}
    return {"ok": False, "error": out.error or "Target connection failed."}


def save_connect_json(body: dict[str, Any]) -> dict[str, Any]:
    """Persist Row Compare credentials server-side (password never in URL)."""
    rc_sid = str(body.get("rc_sid", "")).strip()
    if not rc_sid:
        return {"ok": False, "error": "Session id is required."}

    database = str(body.get("database", "")).strip()
    host = str(body.get("host", "")).strip()
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    port = _parse_int(body.get("port"), 50000)
    server = str(body.get("server", "")).strip()
    az_database = str(body.get("az_database", "")).strip()
    auth_raw = str(body.get("auth_method", "entra")).strip().lower()
    trust = bool(body.get("trust_server_certificate", False))

    missing: list[str] = []
    if not all([database, host, username, password]):
        missing.append("DB2 connection fields")
    if not all([server, az_database]):
        missing.append("Azure connection fields")
    if missing:
        return {"ok": False, "error": "Missing: " + ", ".join(missing)}

    payload_data = {
        "cmp_db2_database": database,
        "cmp_db2_host": host,
        "cmp_db2_port": port,
        "cmp_db2_user": username,
        "cmp_db2_password": password,
        "cmp_az_server": server,
        "cmp_az_database": az_database,
        "cmp_az_auth": auth_raw,
        "cmp_az_trust_cert": trust,
    }

    rc_token_in = str(body.get("rc_token", "")).strip()
    old_payload: dict[str, Any] | None = None
    if has_connect_session(rc_sid):
        if not verify_connect_token(rc_sid, rc_token_in):
            return {"ok": False, "error": "Invalid session token."}
        old_payload = get_connect_payload(rc_sid, rc_token_in)

    invalidate_if_credentials_changed(rc_sid, old_payload, payload_data)

    rc_token = save_connect_payload(rc_sid, payload_data)
    rc_bind = create_bind_token(rc_sid, rc_token)
    return {
        "ok": True,
        "message": "Credentials saved.",
        "rc_token": rc_token,
        "rc_bind": rc_bind,
    }


def check_session_json(body: dict[str, Any]) -> dict[str, Any]:
    rc_sid = str(body.get("rc_sid", "")).strip()
    rc_token = str(body.get("rc_token", "")).strip()
    if not rc_sid or not rc_token:
        return {"ok": True, "active": False}
    return {"ok": True, "active": verify_connect_token(rc_sid, rc_token)}


def create_bind_json(body: dict[str, Any]) -> dict[str, Any]:
    """Issue a one-time bind token so Streamlit can restore credentials (e.g. Edit)."""
    rc_sid = str(body.get("rc_sid", "")).strip()
    rc_token = str(body.get("rc_token", "")).strip()
    if not rc_sid or not rc_token:
        return {"ok": False, "error": "Session id and token are required."}
    if not verify_connect_token(rc_sid, rc_token):
        return {"ok": False, "error": "Invalid or expired session. Connect again."}
    rc_bind = create_bind_token(rc_sid, rc_token)
    return {"ok": True, "rc_bind": rc_bind}


def list_azure_databases_json(body: dict[str, Any]) -> dict[str, Any]:
    server = str(body.get("server", "")).strip()
    auth_raw = str(body.get("auth_method", "entra")).strip().lower()
    auth_method = _AZ_AUTH_MAP.get(auth_raw, "azure_ad_interactive")
    trust = bool(body.get("trust_server_certificate", False))

    if not server:
        return {"ok": False, "error": "Server is required."}

    az_conn = AzureConnection(
        server=server,
        database="master",
        auth_method=auth_method,
        trust_server_certificate=trust,
    )
    list_out = azure_query(
        az_conn,
        "SELECT name FROM sys.databases WHERE state_desc = 'ONLINE' ORDER BY name",
        (),
    )
    if not list_out.ok:
        return {"ok": False, "error": list_out.error or "Failed to list databases."}

    databases = [str(row.get("NAME", "")).strip() for row in list_out.rows]
    databases = [name for name in databases if name]
    if not databases:
        return {"ok": False, "error": "No online databases found on this server."}

    return {"ok": True, "databases": databases, "message": f"Found {len(databases)} database(s)."}
