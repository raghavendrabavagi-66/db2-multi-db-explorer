"""Schema Compare — stitch setup + workspace with GitLab and Azure connectivity."""

from __future__ import annotations

import streamlit as st

from db2_explorer.api.register import ensure_oe_search_api
from db2_explorer.api.sch_credential_store import (
    consume_bind_token,
    get_connect_payload,
    get_connect_token,
)
from db2_explorer.api.sch_result_store import (
    credentials_payload_from_session,
    get_result_snapshot,
    get_result_snapshot_for_session,
    save_result_snapshot,
)
from db2_explorer.clients.azure import AzureConnection
from db2_explorer.compare.schema_compare import run_schema_compare
from db2_explorer.ddl.fetcher import fetch_all_objects
from db2_explorer.gitlab.deployment_parser import OBJECT_TYPE_FILES, parse_all_deployment_files
from db2_explorer.ui.schema_compare_page import (
    SchemaCompareSetupView,
    SchemaCompareWorkspaceView,
    render_schema_compare_setup_page,
    render_schema_compare_workspace_page,
)
from db2_explorer.ui.schema_compare_results import (
    build_objects_map,
    comparison_summary_dict,
    comparison_table_html,
)
from db2_explorer.ui.theme import apply_page

apply_page(title="Schema Compare", layout="wide", schema_compare=True)

_AZ_AUTH_MAP = {
    "entra": "azure_ad_interactive",
    "azure_ad_interactive": "azure_ad_interactive",
    "windows": "windows_integrated",
    "windows_integrated": "windows_integrated",
}


def _init_session() -> None:
    defaults: dict[str, object] = {
        "sch_compare_result": None,
        "sch_deployment_files": {},
        "sch_missing_files": [],
        "sch_bundle_path": "",
        "sch_gitlab_token": "",
        "sch_branch": "",
        "sch_branch_list": [],
        "sch_database": "",
        "sch_db_folder_list": [],
        "sch_server": "",
        "sch_server_folder_list": [],
        "sch_az_server": "",
        "sch_az_database": "",
        "sch_az_database_options": [],
        "sch_az_auth": "entra",
        "sch_az_trust_cert": True,
        "sch_azure_conn": None,
        "sch_selected_object_key": "",
        "sch_setup_done": False,
        "sch_setup_mode": "initial",
        "sch_sid": "",
        "sch_token": "",
        "sch_toast_message": "",
        "sch_toast_error": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _clear_toast() -> None:
    st.session_state.sch_toast_message = ""
    st.session_state.sch_toast_error = False


def _set_toast(message: str, *, error: bool = False) -> None:
    st.session_state.sch_toast_message = message
    st.session_state.sch_toast_error = error


def _azure_auth_method() -> str:
    raw = str(st.session_state.get("sch_az_auth", "entra")).lower()
    return _AZ_AUTH_MAP.get(raw, "azure_ad_interactive")


def _apply_sch_bind() -> bool:
    bind = str(st.query_params.get("sch_bind", "")).strip()
    if not bind:
        return False
    pair = consume_bind_token(bind)
    if not pair:
        return False
    sid, token = pair
    payload = get_connect_payload(sid, token)
    if not payload:
        return False
    for key, val in payload.items():
        st.session_state[key] = val
    st.session_state.sch_sid = sid
    st.session_state.sch_token = token
    return True


def _restore_from_session_cache() -> bool:
    sid = str(st.session_state.get("sch_sid", "")).strip()
    if not sid:
        return False
    token = str(st.session_state.get("sch_token", "")).strip()
    if not token:
        token = get_connect_token(sid) or ""
        if token:
            st.session_state.sch_token = token
    if not token:
        return False
    payload = get_connect_payload(sid, token)
    if not payload:
        return False
    for key, val in payload.items():
        st.session_state[key] = val
    st.session_state.sch_sid = sid
    st.session_state.sch_token = token
    return True


def _session_credentials() -> dict[str, object]:
    return credentials_payload_from_session(dict(st.session_state))


def _lookup_result_snapshot() -> dict[str, object] | None:
    sid = str(st.session_state.get("sch_sid", "")).strip()
    token = str(st.session_state.get("sch_token", "")).strip()
    if sid and token:
        snapshot = get_result_snapshot_for_session(sid, token)
        if snapshot:
            return snapshot
    if sid:
        return get_result_snapshot(sid, _session_credentials())
    return None


def _ensure_setup_credentials() -> None:
    if st.session_state.get("sch_setup_mode") != "edit":
        return
    if (
        str(st.session_state.get("sch_gitlab_token", "")).strip()
        and st.session_state.get("sch_deployment_files")
    ):
        return
    _restore_from_session_cache()


def _run_schema_compare() -> None:
    deployment_files = dict(st.session_state.get("sch_deployment_files") or {})
    if not deployment_files:
        _set_toast("Load deployment from GitLab first.", error=True)
        return

    az_server = str(st.session_state.get("sch_az_server", "")).strip()
    az_database = str(st.session_state.get("sch_az_database", "")).strip()
    if not all([az_server, az_database]):
        _set_toast("Azure server and database are required.", error=True)
        return

    azure_conn = AzureConnection(
        server=az_server,
        database=az_database,
        auth_method=_azure_auth_method(),
        trust_server_certificate=bool(st.session_state.get("sch_az_trust_cert", True)),
    )
    gitlab_objects = parse_all_deployment_files(deployment_files)
    types = list(OBJECT_TYPE_FILES.keys())
    db_objects, fetch_err = fetch_all_objects(azure_conn, types)
    compare_result = run_schema_compare(gitlab_objects, db_objects)
    compare_result.missing_files = list(st.session_state.get("sch_missing_files") or [])
    compare_result.bundle_path = str(st.session_state.get("sch_bundle_path") or "")
    st.session_state.sch_compare_result = compare_result
    st.session_state.sch_azure_conn = azure_conn

    source_label = str(st.session_state.get("sch_database") or "GitLab Source")
    target_label = az_database
    summary = comparison_summary_dict(compare_result)
    table_html = comparison_table_html(compare_result)
    objects_map = build_objects_map(compare_result)

    sid = str(st.session_state.get("sch_sid", "")).strip()
    if sid:
        save_result_snapshot(
            sid,
            _session_credentials(),
            summary=summary,
            table_html=table_html,
            objects=objects_map,
            source_label=source_label,
            target_label=target_label,
            bundle_path=compare_result.bundle_path,
        )

    total = summary["total"]
    message = f"Schema comparison complete — {total} object(s)."
    if fetch_err:
        message += f" Warning: {fetch_err}"
    _set_toast(message)


def _handle_query_actions() -> None:
    action = st.query_params.get("sch_action", "")
    if not action:
        return

    restored = _apply_sch_bind() or _restore_from_session_cache()

    if action == "connect":
        if not restored:
            _set_toast("Session expired — connect again.", error=True)
            st.query_params.clear()
            return
        missing = []
        if not str(st.session_state.get("sch_gitlab_token", "")).strip():
            missing.append("GitLab token")
        if not st.session_state.get("sch_deployment_files"):
            missing.append("deployment files")
        if not all([st.session_state.sch_az_server, st.session_state.sch_az_database]):
            missing.append("Azure connection fields")
        if missing:
            _set_toast("Missing: " + ", ".join(missing), error=True)
        else:
            from_edit = st.session_state.get("sch_setup_mode") == "edit"
            st.session_state.sch_setup_done = True
            st.session_state.sch_setup_mode = "initial"
            if from_edit:
                if _lookup_result_snapshot():
                    _set_toast("Credentials updated.")
                else:
                    _run_schema_compare()
            else:
                _run_schema_compare()
    elif action == "edit":
        if not restored:
            _restore_from_session_cache()
        if not str(st.session_state.get("sch_gitlab_token", "")).strip():
            _set_toast("Session expired — connect again.", error=True)
            st.session_state.sch_setup_done = True
            st.session_state.sch_setup_mode = "initial"
            st.query_params.clear()
            return
        st.session_state.sch_setup_mode = "edit"
        st.session_state.sch_setup_done = False
        _set_toast("Edit connection settings below.")
    elif action == "back":
        if not restored:
            _restore_from_session_cache()
        st.session_state.sch_setup_mode = "initial"
        st.session_state.sch_setup_done = True
        snapshot = _lookup_result_snapshot()
        if snapshot and not st.session_state.get("sch_compare_result"):
            _set_toast("Returned to comparison results.")
    elif action == "refresh":
        if not restored:
            _restore_from_session_cache()
        st.session_state.sch_setup_done = True
        _run_schema_compare()

    st.query_params.clear()


def _setup_view() -> SchemaCompareSetupView:
    deployment_files = st.session_state.get("sch_deployment_files") or {}
    return SchemaCompareSetupView(
        gitlab_token=str(st.session_state.get("sch_gitlab_token", "")),
        branch=str(st.session_state.get("sch_branch", "")),
        branch_list=list(st.session_state.get("sch_branch_list", [])),
        database=str(st.session_state.get("sch_database", "")),
        db_folder_list=list(st.session_state.get("sch_db_folder_list", [])),
        server=str(st.session_state.get("sch_server", "")),
        server_folder_list=list(st.session_state.get("sch_server_folder_list", [])),
        az_server=str(st.session_state.get("sch_az_server", "")),
        az_database=str(st.session_state.get("sch_az_database", "")),
        az_database_options=list(st.session_state.get("sch_az_database_options", [])),
        az_auth=str(st.session_state.get("sch_az_auth", "entra")),
        az_trust_cert=bool(st.session_state.get("sch_az_trust_cert", True)),
        deployment_loaded=bool(deployment_files),
        bundle_path=str(st.session_state.get("sch_bundle_path", "")),
        deployment_files=dict(deployment_files),
        missing_files=list(st.session_state.get("sch_missing_files") or []),
        edit_mode=st.session_state.get("sch_setup_mode") == "edit",
        sch_sid=str(st.session_state.get("sch_sid", "")),
        sch_token=str(st.session_state.get("sch_token", "")),
        toast_message=str(st.session_state.get("sch_toast_message", "")),
        toast_error=bool(st.session_state.get("sch_toast_error", False)),
    )


def _workspace_view() -> SchemaCompareWorkspaceView:
    snapshot = _lookup_result_snapshot()
    if snapshot:
        summary = dict(snapshot.get("summary") or {})
        return SchemaCompareWorkspaceView(
            source_label=str(snapshot.get("source_label") or st.session_state.get("sch_database") or "GitLab Source"),
            target_label=str(snapshot.get("target_label") or st.session_state.get("sch_az_database") or "Azure SQL Target"),
            summary=summary,
            table_html=str(snapshot.get("table_html") or ""),
            objects=dict(snapshot.get("objects") or {}),
            selected_object_key=str(snapshot.get("selected_object_key") or ""),
            has_results=bool(snapshot.get("table_html")),
            sch_sid=str(st.session_state.get("sch_sid", "")),
            sch_token=str(st.session_state.get("sch_token", "")),
            toast_message=str(st.session_state.get("sch_toast_message", "")),
            toast_error=bool(st.session_state.get("sch_toast_error", False)),
        )

    return SchemaCompareWorkspaceView(
        source_label=str(st.session_state.get("sch_database") or "GitLab Source"),
        target_label=str(st.session_state.get("sch_az_database") or "Azure SQL Target"),
        sch_sid=str(st.session_state.get("sch_sid", "")),
        sch_token=str(st.session_state.get("sch_token", "")),
        toast_message=str(st.session_state.get("sch_toast_message", "")),
        toast_error=bool(st.session_state.get("sch_toast_error", False)),
    )


_init_session()
ensure_oe_search_api()
_handle_query_actions()
_ensure_setup_credentials()

if st.session_state.sch_setup_done:
    render_schema_compare_workspace_page(_workspace_view())
else:
    render_schema_compare_setup_page(_setup_view())

_clear_toast()
