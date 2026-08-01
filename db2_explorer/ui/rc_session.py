"""Row Compare session lifecycle — clear credentials and results on home navigation."""

from __future__ import annotations

import streamlit as st

RC_CLEAR_QUERY_PARAM = "rc_clear"

RC_SESSION_KEYS = (
    "compare_result",
    "compare_ran_at",
    "cmp_compare_scope",
    "cmp_source_table_list",
    "cmp_db2_schema",
    "cmp_azure_schema",
    "cmp_target_table_mode",
    "cmp_db2_database",
    "cmp_db2_host",
    "cmp_db2_port",
    "cmp_db2_user",
    "cmp_db2_password",
    "cmp_az_server",
    "cmp_az_database",
    "cmp_az_database_options",
    "cmp_az_auth",
    "cmp_az_trust_cert",
    "rc_setup_done",
    "rc_toast_message",
    "rc_toast_error",
)


def row_compare_home_clear_url() -> str:
    """Home URL that triggers Row Compare session reset."""
    return f"/?{RC_CLEAR_QUERY_PARAM}=1"


def clear_row_compare_session() -> None:
    """Drop all Row Compare session keys, including credentials and results."""
    for key in RC_SESSION_KEYS:
        st.session_state.pop(key, None)


def handle_row_compare_home_clear() -> None:
    """Clear Row Compare session when navigating home via ``?rc_clear=1``."""
    if st.query_params.get(RC_CLEAR_QUERY_PARAM) != "1":
        return
    clear_row_compare_session()
    st.query_params.clear()
