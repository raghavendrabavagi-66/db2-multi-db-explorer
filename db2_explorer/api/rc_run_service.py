"""Row Compare run API — execute comparison and return JSON for iframe updates."""

from __future__ import annotations

from typing import Any

from db2_explorer.api.rc_credential_store import get_connect_payload
from db2_explorer.clients.azure import AzureConnection
from db2_explorer.compare.row_compare import comparison_metrics, run_comparison
from db2_explorer.data.connections import Connection
from db2_explorer.ui.row_compare_page import _comparison_rows_html

_AZ_AUTH_MAP = {
    "entra": "azure_ad_interactive",
    "azure_ad_interactive": "azure_ad_interactive",
    "windows": "windows_integrated",
    "windows_integrated": "windows_integrated",
}


def _azure_auth_method(raw: str) -> str:
    return _AZ_AUTH_MAP.get(str(raw or "entra").lower(), "azure_ad_interactive")


def run_comparison_json(body: dict[str, Any]) -> dict[str, Any]:
    """Run Row Compare using credentials stored for ``rc_sid``."""
    rc_sid = str(body.get("rc_sid", "")).strip()
    if not rc_sid:
        return {"ok": False, "error": "Session id is required."}

    payload = get_connect_payload(rc_sid)
    if not payload:
        return {"ok": False, "error": "Connection not found. Connect again from setup."}

    db2_database = str(payload.get("cmp_db2_database", "")).strip()
    db2_host = str(payload.get("cmp_db2_host", "")).strip()
    db2_user = str(payload.get("cmp_db2_user", "")).strip()
    db2_password = str(payload.get("cmp_db2_password", ""))
    db2_port = int(payload.get("cmp_db2_port", 50000))
    az_server = str(payload.get("cmp_az_server", "")).strip()
    az_database = str(payload.get("cmp_az_database", "")).strip()

    target_table_mode = str(body.get("target_table_mode", "original")).strip()
    if target_table_mode not in {"original", "staging"}:
        target_table_mode = "original"

    db2_schema = str(body.get("db2_schema") or payload.get("cmp_db2_schema") or "USERID").strip()
    azure_schema = str(body.get("azure_schema") or payload.get("cmp_azure_schema") or "dbo").strip()

    errors: list[str] = []
    if not all([db2_database, db2_host, db2_user, db2_password]):
        errors.append("DB2 credentials are incomplete.")
    if not all([az_server, az_database]):
        errors.append("Azure credentials are incomplete.")
    if not db2_schema or not azure_schema:
        errors.append("Schema names are required.")
    if errors:
        return {"ok": False, "error": " ".join(errors)}

    db2_conn = Connection(dbname=db2_database, host=db2_host, port=db2_port)
    azure_conn = AzureConnection(
        server=az_server,
        database=az_database,
        auth_method=_azure_auth_method(str(payload.get("cmp_az_auth", "entra"))),
        trust_server_certificate=bool(payload.get("cmp_az_trust_cert", True)),
    )

    result = run_comparison(
        db2_conn,
        db2_user,
        db2_password,
        db2_schema,
        azure_conn,
        azure_schema,
        target_table_mode=target_table_mode,
        selected_tables=None,
    )

    if result.status != "ok":
        return {"ok": False, "error": result.error or "Comparison failed."}

    records = result.comparison.to_dict(orient="records")
    metrics = comparison_metrics(result.comparison)
    metrics["rows_label"] = f"{metrics.get('tables_source', 0):,}"

    return {
        "ok": True,
        "message": f"Comparison complete — {len(result.comparison)} table(s).",
        "metrics": metrics,
        "tbody_html": _comparison_rows_html(records),
        "table_count": len(result.comparison),
    }
