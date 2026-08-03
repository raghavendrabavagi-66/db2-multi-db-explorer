"""Schema Compare session lifecycle — clear credentials and results on home navigation."""

from __future__ import annotations

import streamlit as st

from db2_explorer.api.sch_credential_store import clear_connect_payload
from db2_explorer.api.sch_result_store import clear_result_snapshot

SCH_CLEAR_QUERY_PARAM = "sch_clear"

SCH_SESSION_KEYS = (
    "sch_compare_result",
    "sch_deployment_files",
    "sch_missing_files",
    "sch_bundle_path",
    "sch_gitlab_token",
    "sch_branch",
    "sch_branch_list",
    "sch_database",
    "sch_db_folder_list",
    "sch_server",
    "sch_server_folder_list",
    "sch_az_server",
    "sch_az_database",
    "sch_az_database_options",
    "sch_az_auth",
    "sch_az_trust_cert",
    "sch_azure_conn",
    "sch_selected_object_key",
    "sch_selected_object_type",
    "sch_status_bucket",
    "sch_search",
    "sch_apply_log",
    "sch_setup_done",
    "sch_setup_mode",
    "sch_sid",
    "sch_token",
    "sch_toast_message",
    "sch_toast_error",
    "sch_pending_refresh",
    "sch_clear_secrets",
)


def schema_compare_home_clear_url() -> str:
    """Home URL that triggers Schema Compare session reset."""
    return f"/?{SCH_CLEAR_QUERY_PARAM}=1"


def clear_schema_compare_session() -> None:
    """Drop all Schema Compare session keys, including credentials and results."""
    sid = str(st.session_state.get("sch_sid", "")).strip()
    if sid:
        clear_connect_payload(sid)
        clear_result_snapshot(sid)
    for key in SCH_SESSION_KEYS:
        st.session_state.pop(key, None)


def handle_schema_compare_home_clear() -> None:
    """Clear Schema Compare session when navigating home via ``?sch_clear=1``."""
    if st.query_params.get(SCH_CLEAR_QUERY_PARAM) != "1":
        return
    clear_schema_compare_session()
    st.query_params.clear()
