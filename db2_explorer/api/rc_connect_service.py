"""Row Compare connection test helpers for the background API server."""

from __future__ import annotations

from typing import Any

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
