"""Row Compare — stitch setup + workspace with DB2 and Azure connectivity."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from db2_explorer.api.register import ensure_oe_search_api
from db2_explorer.api.rc_credential_store import consume_bind_token, get_connect_payload
from db2_explorer.clients.azure import AUTH_METHOD_LABELS, AzureConnection
from db2_explorer.data.connections import Connection
from db2_explorer.compare.row_compare import (
    CompareResult,
    comparison_metrics,
    run_comparison,
)
from db2_explorer.ui.row_compare_page import (
    RowCompareSetupView,
    RowCompareWorkspaceView,
    render_row_compare_setup_page,
    render_row_compare_workspace_page,
)
from db2_explorer.ui.row_compare_results import comparison_rows_html, comparison_tbody_views
from db2_explorer.ui.theme import apply_page

apply_page(title="Row Compare", layout="wide")

_AZ_AUTH_MAP = {
    "entra": "azure_ad_interactive",
    "azure_ad_interactive": "azure_ad_interactive",
    "windows": "windows_integrated",
    "windows_integrated": "windows_integrated",
}


def _init_session() -> None:
    defaults: dict[str, object] = {
        "compare_result": None,
        "compare_ran_at": None,
        "cmp_compare_scope": "all",
        "cmp_source_table_list": [],
        "cmp_db2_schema": "USERID",
        "cmp_azure_schema": "dbo",
        "cmp_target_table_mode": "original",
        "cmp_db2_database": "",
        "cmp_db2_host": "",
        "cmp_db2_port": 50000,
        "cmp_db2_user": "",
        "cmp_db2_password": "",
        "cmp_az_server": "",
        "cmp_az_database": "",
        "cmp_az_database_options": [],
        "cmp_az_auth": "entra",
        "cmp_az_trust_cert": True,
        "rc_setup_done": False,
        "rc_setup_mode": "initial",
        "rc_sid": "",
        "rc_token": "",
        "rc_toast_message": "",
        "rc_toast_error": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _clear_toast() -> None:
    st.session_state.rc_toast_message = ""
    st.session_state.rc_toast_error = False


def _set_toast(message: str, *, error: bool = False) -> None:
    st.session_state.rc_toast_message = message
    st.session_state.rc_toast_error = error


def _apply_connect_params() -> None:
    st.session_state.cmp_db2_database = st.query_params.get("cmp_db2_database", "")
    st.session_state.cmp_db2_host = st.query_params.get("cmp_db2_host", "")
    try:
        st.session_state.cmp_db2_port = int(st.query_params.get("cmp_db2_port", "50000"))
    except ValueError:
        st.session_state.cmp_db2_port = 50000
    st.session_state.cmp_db2_user = st.query_params.get("cmp_db2_user", "")
    password = st.query_params.get("cmp_db2_password")
    if password:
        st.session_state.cmp_db2_password = password
    st.session_state.cmp_az_server = st.query_params.get("cmp_az_server", "")
    st.session_state.cmp_az_database = st.query_params.get("cmp_az_database", "")
    st.session_state.cmp_az_auth = st.query_params.get("cmp_az_auth", "entra")
    st.session_state.cmp_az_trust_cert = st.query_params.get("cmp_az_trust_cert", "1") == "1"


def _apply_rc_bind() -> bool:
    """Bind Streamlit session from a one-time ``rc_bind`` query param."""
    bind = str(st.query_params.get("rc_bind", "")).strip()
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
    st.session_state.rc_sid = sid
    st.session_state.rc_token = token
    return True


def _restore_from_session_cache() -> bool:
    """Reload credentials from the server cache using session_state sid + token."""
    sid = str(st.session_state.get("rc_sid", "")).strip()
    token = str(st.session_state.get("rc_token", "")).strip()
    if not sid or not token:
        return False
    payload = get_connect_payload(sid, token)
    if not payload:
        return False
    for key, val in payload.items():
        st.session_state[key] = val
    return True


def _ensure_az_database_in_options() -> None:
    """Keep the selected Azure database visible in the setup dropdown."""
    az_db = str(st.session_state.get("cmp_az_database", "")).strip()
    if not az_db:
        return
    options = list(st.session_state.get("cmp_az_database_options", []))
    if az_db not in options:
        st.session_state.cmp_az_database_options = [az_db, *options]


def _handle_query_actions() -> None:
    action = st.query_params.get("rc_action", "")
    if not action:
        return

    restored = _apply_rc_bind() or _restore_from_session_cache()

    if action == "connect":
        if not restored:
            _apply_connect_params()
        missing = []
        if not all([
            st.session_state.cmp_db2_database,
            st.session_state.cmp_db2_host,
            st.session_state.cmp_db2_user,
            st.session_state.cmp_db2_password,
        ]):
            missing.append("DB2 connection fields")
        if not all([st.session_state.cmp_az_server, st.session_state.cmp_az_database]):
            missing.append("Azure connection fields")
        if missing:
            _set_toast("Missing: " + ", ".join(missing), error=True)
        else:
            st.session_state.rc_setup_done = True
            st.session_state.rc_setup_mode = "initial"
            st.session_state.compare_result = None
            _set_toast("Connected — ready to run comparison.")
    elif action == "edit":
        if not restored:
            _restore_from_session_cache()
        _ensure_az_database_in_options()
        st.session_state.rc_setup_mode = "edit"
        st.session_state.rc_setup_done = False
        _set_toast("Edit connection settings below.")
    elif action == "back":
        st.session_state.rc_setup_mode = "initial"
        st.session_state.rc_setup_done = True
    elif action == "run":
        if not restored:
            _restore_from_session_cache()
        mode = st.query_params.get("cmp_target_table_mode", "original")
        if mode in {"original", "staging"}:
            st.session_state.cmp_target_table_mode = mode
        st.session_state.rc_setup_done = True
        _run_comparison()

    st.query_params.clear()


def _azure_auth_method() -> str:
    raw = str(st.session_state.get("cmp_az_auth", "entra")).lower()
    return _AZ_AUTH_MAP.get(raw, "azure_ad_interactive")


def _run_comparison() -> None:
    db2_database = str(st.session_state.get("cmp_db2_database", "")).strip()
    db2_host = str(st.session_state.get("cmp_db2_host", "")).strip()
    db2_user = str(st.session_state.get("cmp_db2_user", "")).strip()
    db2_password = str(st.session_state.get("cmp_db2_password", ""))
    db2_port = int(st.session_state.get("cmp_db2_port", 50000))
    db2_schema = str(st.session_state.get("cmp_db2_schema", "USERID")).strip()
    azure_schema = str(st.session_state.get("cmp_azure_schema", "dbo")).strip()
    az_server = str(st.session_state.get("cmp_az_server", "")).strip()
    az_database = str(st.session_state.get("cmp_az_database", "")).strip()
    target_table_mode = str(st.session_state.get("cmp_target_table_mode", "original"))

    errors: list[str] = []
    if not all([db2_database, db2_host, db2_user, db2_password]):
        errors.append("DB2 credentials are incomplete.")
    if not all([az_server, az_database]):
        errors.append("Azure credentials are incomplete.")
    if not db2_schema or not azure_schema:
        errors.append("Schema names are required.")
    if errors:
        _set_toast(" ".join(errors), error=True)
        st.session_state.rc_setup_done = True
        return

    db2_conn = Connection(dbname=db2_database, host=db2_host, port=db2_port)
    azure_conn = AzureConnection(
        server=az_server,
        database=az_database,
        auth_method=_azure_auth_method(),
        trust_server_certificate=bool(st.session_state.get("cmp_az_trust_cert", True)),
    )

    with st.spinner("Running comparison…"):
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
        _set_toast(result.error or "Comparison failed.", error=True)
        st.session_state.rc_setup_done = True
        return

    st.session_state.compare_result = result
    st.session_state.compare_ran_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _set_toast(f"Comparison complete — {len(result.comparison)} table(s).")


def _setup_view() -> RowCompareSetupView:
    return RowCompareSetupView(
        db2_database=str(st.session_state.get("cmp_db2_database", "")),
        db2_host=str(st.session_state.get("cmp_db2_host", "")),
        db2_port=int(st.session_state.get("cmp_db2_port", 50000)),
        db2_user=str(st.session_state.get("cmp_db2_user", "")),
        db2_password=str(st.session_state.get("cmp_db2_password", "")),
        az_server=str(st.session_state.get("cmp_az_server", "")),
        az_database=str(st.session_state.get("cmp_az_database", "")),
        az_database_options=list(st.session_state.get("cmp_az_database_options", [])),
        az_auth=str(st.session_state.get("cmp_az_auth", "entra")),
        az_trust_cert=bool(st.session_state.get("cmp_az_trust_cert", True)),
        edit_mode=st.session_state.get("rc_setup_mode") == "edit",
        rc_sid=str(st.session_state.get("rc_sid", "")),
        rc_token=str(st.session_state.get("rc_token", "")),
        toast_message=str(st.session_state.get("rc_toast_message", "")),
        toast_error=bool(st.session_state.get("rc_toast_error", False)),
    )


def _workspace_view() -> RowCompareWorkspaceView:
    result: CompareResult | None = st.session_state.get("compare_result")
    metrics: dict[str, object] = {}
    rows_html = comparison_rows_html([])
    tbody_views: dict[str, str] = {}
    has_results = False

    if result is not None and result.status == "ok" and not result.comparison.empty:
        has_results = True
        metrics = comparison_metrics(result.comparison)
        metrics["rows_label"] = f"{metrics.get('tables_source', 0):,}"
        records = result.comparison.to_dict(orient="records")
        tbody_views = comparison_tbody_views(records)
        rows_html = tbody_views.get("all", comparison_rows_html(records))

    auth = _azure_auth_method()
    return RowCompareWorkspaceView(
        db2_database=str(st.session_state.get("cmp_db2_database", "")),
        db2_host=str(st.session_state.get("cmp_db2_host", "")),
        db2_port=int(st.session_state.get("cmp_db2_port", 50000)),
        az_server=str(st.session_state.get("cmp_az_server", "")),
        az_database=str(st.session_state.get("cmp_az_database", "")),
        az_auth_label=AUTH_METHOD_LABELS.get(auth, auth),
        target_table_mode=str(st.session_state.get("cmp_target_table_mode", "original")),
        metrics=metrics,
        result_rows_html=rows_html,
        result_tbody_views=tbody_views,
        has_results=has_results,
        rc_sid=str(st.session_state.get("rc_sid", "")),
        rc_token=str(st.session_state.get("rc_token", "")),
        toast_message=str(st.session_state.get("rc_toast_message", "")),
        toast_error=bool(st.session_state.get("rc_toast_error", False)),
    )


_init_session()
ensure_oe_search_api()
_handle_query_actions()

if st.session_state.rc_setup_done:
    render_row_compare_workspace_page(_workspace_view())
else:
    render_row_compare_setup_page(_setup_view())

_clear_toast()
