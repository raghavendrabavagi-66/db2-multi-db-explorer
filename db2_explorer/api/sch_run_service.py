"""Schema Compare run API — execute comparison and return JSON for iframe updates."""

from __future__ import annotations

from typing import Any

from db2_explorer.api.sch_credential_store import get_connect_payload
from db2_explorer.api.sch_result_store import save_result_snapshot
from db2_explorer.clients.azure import AzureConnection
from db2_explorer.compare.schema_compare import run_schema_compare
from db2_explorer.ddl.fetcher import fetch_all_objects
from db2_explorer.gitlab.deployment_parser import OBJECT_TYPE_FILES, parse_all_deployment_files
from db2_explorer.ui.schema_compare_results import (
    build_objects_map,
    comparison_summary_dict,
    comparison_table_html,
)

_AZ_AUTH_MAP = {
    "entra": "azure_ad_interactive",
    "azure_ad_interactive": "azure_ad_interactive",
    "windows": "windows_integrated",
    "windows_integrated": "windows_integrated",
}


def _azure_auth_method(raw: str) -> str:
    return _AZ_AUTH_MAP.get(str(raw or "entra").lower(), "azure_ad_interactive")


def run_schema_compare_json(body: dict[str, Any]) -> dict[str, Any]:
    """Run Schema Compare using credentials stored for ``sch_sid``."""
    sch_sid = str(body.get("sch_sid", "")).strip()
    sch_token = str(body.get("sch_token", "")).strip()
    if not sch_sid:
        return {"ok": False, "error": "Session id is required."}
    if not sch_token:
        return {"ok": False, "error": "Session token is required."}

    payload = get_connect_payload(sch_sid, sch_token)
    if not payload:
        return {"ok": False, "error": "Connection not found. Connect again from setup."}

    deployment_files = dict(payload.get("sch_deployment_files") or {})
    if not deployment_files:
        return {"ok": False, "error": "Deployment files not loaded. Load deployment from setup."}

    az_server = str(payload.get("sch_az_server", "")).strip()
    az_database = str(payload.get("sch_az_database", "")).strip()
    if not all([az_server, az_database]):
        return {"ok": False, "error": "Azure server and database are required."}

    azure_conn = AzureConnection(
        server=az_server,
        database=az_database,
        auth_method=_azure_auth_method(str(payload.get("sch_az_auth", "entra"))),
        trust_server_certificate=bool(payload.get("sch_az_trust_cert", True)),
    )

    gitlab_objects = parse_all_deployment_files(deployment_files)
    types = list(OBJECT_TYPE_FILES.keys())
    db_objects, fetch_err = fetch_all_objects(azure_conn, types)
    compare_result = run_schema_compare(gitlab_objects, db_objects)
    compare_result.missing_files = list(payload.get("sch_missing_files") or [])
    compare_result.bundle_path = str(payload.get("sch_bundle_path") or "")

    source_label = str(payload.get("sch_database") or "GitLab Source")
    target_label = az_database
    summary = comparison_summary_dict(compare_result)
    table_html = comparison_table_html(compare_result)
    objects_map = build_objects_map(compare_result)

    cred_keys = {
        "sch_gitlab_token": str(payload.get("sch_gitlab_token", "")),
        "sch_branch": str(payload.get("sch_branch", "")),
        "sch_database": str(payload.get("sch_database", "")),
        "sch_server": str(payload.get("sch_server", "")),
        "sch_az_server": az_server,
        "sch_az_database": az_database,
        "sch_az_auth": str(payload.get("sch_az_auth", "entra")),
        "sch_az_trust_cert": bool(payload.get("sch_az_trust_cert", True)),
    }

    save_result_snapshot(
        sch_sid,
        cred_keys,
        summary=summary,
        table_html=table_html,
        objects=objects_map,
        source_label=source_label,
        target_label=target_label,
        bundle_path=compare_result.bundle_path,
    )

    total = summary["identical"] + summary["different"] + summary["only_gitlab"] + summary["only_db"]
    message = f"Schema comparison complete — {total} object(s)."
    if fetch_err:
        message += f" Warning: {fetch_err}"

    return {
        "ok": True,
        "message": message,
        "summary": summary,
        "table_html": table_html,
        "objects": objects_map,
        "source_label": source_label,
        "target_label": target_label,
        "total_objects": total,
    }
