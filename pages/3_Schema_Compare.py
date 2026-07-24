"""Schema Compare — GitLab deployment DDL vs live target database."""

from __future__ import annotations

import streamlit.components.v1 as components

import pandas as pd
import streamlit as st

from azure_client import AUTH_METHOD_LABELS, AzureConnection, test_connection as test_azure
from azure_ddl_fetcher import fetch_all_objects
from deployment_parser import OBJECT_TYPE_FILES, parse_all_deployment_files
from gitlab_client import (
    GITLAB_BASE_URL,
    GITLAB_PROJECT_ID,
    GitLabClient,
    make_gitlab_config,
)
from constraint_summary import fk_summary_table
from schema_compare_engine import ObjectCompareResult, filter_results, run_schema_compare

st.set_page_config(page_title="Schema Compare", layout="wide")

# 60% scrollable object list + 40% pinned bottom DDL pane
st.markdown(
    """
    <style>
    /* Top object navigator — capped height with internal scroll */
    .st-key-sch_objects_pane {
        max-height: calc(60vh - 8rem) !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
    }
    .st-key-sch_objects_pane [data-testid="stVerticalBlockBorderWrapper"] {
        max-height: calc(60vh - 8rem) !important;
        overflow-y: auto !important;
    }
    /* Native Streamlit bottom container (st.bottom / st._bottom) */
    [data-testid="stBottomBlockContainer"] {
        max-height: 40vh !important;
        overflow-y: auto !important;
        background: #ffffff !important;
        border-top: 1px solid #e0e0e0 !important;
        box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.1) !important;
    }
    [data-testid="stBottomBlockContainer"] iframe {
        height: calc(40vh - 11rem) !important;
        min-height: 160px !important;
    }
    /* Fallback when st.bottom is unavailable — fixed pane + main padding */
    section.main:has(.sch-ddl-open-marker) {
        padding-bottom: calc(40vh + 1.5rem) !important;
    }
    section.main .st-key-sch_ddl_pane {
        position: fixed !important;
        bottom: 0 !important;
        left: 5.5rem !important;
        right: 1.25rem !important;
        height: 40vh !important;
        max-height: 40vh !important;
        overflow-y: auto !important;
        z-index: 999 !important;
        background: #ffffff !important;
        box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.12) !important;
        border-top: 1px solid #e0e0e0 !important;
    }
    section.main .st-key-sch_ddl_pane iframe {
        height: calc(40vh - 11rem) !important;
        min-height: 160px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Fallback iframe height when CSS calc is not applied (components.html requires pixels)
_DDL_IFRAME_HEIGHT = 260

_STATUS_ICON = {
    "identical": "✓",
    "different": "✗",
    "only_gitlab": "+",
    "only_db": "◌",
}

_TYPE_LABELS = {
    "SCHEMA": "Schemas",
    "SEQUENCE": "Sequences",
    "TABLE": "Tables",
    "CONSTRAINT": "Constraints",
    "INDEX": "Indexes",
    "VIEW": "Views",
    "FUNCTION": "Functions",
    "PROCEDURE": "Procedures",
    "MQT_IMMEDIATE": "MQT Immediate",
    "MQT_DEFERRED": "MQT Deferred",
    "TRIGGER": "Triggers",
    "ROLE": "Roles",
}


def _type_summary(items: list[ObjectCompareResult]) -> str:
    if not items:
        return "0 objects"
    identical = sum(1 for i in items if i.status == "identical")
    different = sum(1 for i in items if i.status == "different")
    only_gl = sum(1 for i in items if i.status == "only_gitlab")
    only_db = sum(1 for i in items if i.status == "only_db")
    parts = [f"{len(items)} objects"]
    if identical:
        parts.append(f"{identical} identical")
    if different:
        parts.append(f"{different} different")
    if only_gl:
        parts.append(f"{only_gl} only GitLab")
    if only_db:
        parts.append(f"{only_db} only DB")
    return ", ".join(parts)


def _get_bottom_container():
    """Streamlit pinned bottom container (public or legacy private API)."""
    bottom = getattr(st, "bottom", None)
    if bottom is not None:
        return bottom
    return getattr(st, "_bottom", None)


def _resolve_selected(result) -> ObjectCompareResult | None:
    key = st.session_state.get("sch_selected_object_key", "")
    if not key:
        return None
    for items in result.by_type.values():
        for item in items:
            if item.object_key == key:
                return item
    return None


def _render_ddl_pane(selected: ObjectCompareResult) -> None:
    st.subheader("DDL comparison")
    src_file = selected.source_file or OBJECT_TYPE_FILES.get(selected.object_type, "")
    line_info = f" · line {selected.gitlab_line}" if selected.gitlab_line else ""
    st.caption(
        f"**{selected.object_type}** · `{selected.schema}.{selected.name}`"
        + (f" on `{selected.parent}`" if selected.parent else "")
        + f" · {src_file}{line_info}"
        + f" · status: **{selected.status}**"
    )
    tab_sql, tab_summary = st.tabs(["SQL view", "Summary view"])
    with tab_sql:
        components.html(selected.diff_html, height=_DDL_IFRAME_HEIGHT, scrolling=True)
    with tab_summary:
        st.table(
            {
                "Property": ["Status", "Object type", "Schema", "Name", "Parent table", "Source file", "GitLab line"],
                "Value": [
                    selected.status,
                    selected.object_type,
                    selected.schema,
                    selected.name,
                    selected.parent or "—",
                    src_file,
                    str(selected.gitlab_line or "—"),
                ],
            }
        )
        fk_rows = fk_summary_table(selected.gitlab_ddl, selected.db_ddl)
        if fk_rows:
            st.markdown("**Foreign key properties**")
            fk_df = pd.DataFrame(fk_rows)
            st.dataframe(
                fk_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Match": st.column_config.TextColumn(width="small"),
                },
            )
            mismatches = [r for r in fk_rows if r["Match"] == "no"]
            if mismatches:
                props = ", ".join(r["Property"] for r in mismatches)
                st.warning(f"Mismatch: {props}")
        if selected.status == "different":
            st.warning("Definitions differ after normalization — review inline highlights in SQL view.")
        elif selected.status == "identical":
            st.success("Definitions match.")
        elif selected.status == "only_gitlab":
            st.warning("Object exists in GitLab deployment but was not found in the target database.")
        else:
            st.warning("Object exists in the database but is not in the GitLab deployment files.")


def _apply_pending_branch() -> None:
    """Apply branch from migration_info before the branch selectbox is drawn."""
    pending = st.session_state.pop("sch_pending_branch", None)
    if not pending:
        return
    if pending not in st.session_state.sch_branch_list:
        st.session_state.sch_branch_list = sorted(
            set(st.session_state.sch_branch_list) | {pending}
        )
    st.session_state.sch_branch = pending


if "sch_compare_result" not in st.session_state:
    st.session_state.sch_compare_result = None
if "sch_deployment_files" not in st.session_state:
    st.session_state.sch_deployment_files = {}
if "sch_missing_files" not in st.session_state:
    st.session_state.sch_missing_files = []
if "sch_bundle_path" not in st.session_state:
    st.session_state.sch_bundle_path = ""
if "sch_selected_object_key" not in st.session_state:
    st.session_state.sch_selected_object_key = ""
if "sch_selected_object_type" not in st.session_state:
    st.session_state.sch_selected_object_type = ""
if "sch_branch_list" not in st.session_state:
    st.session_state.sch_branch_list = []

st.title("Schema Compare")
st.caption("Compare GitLab deployment DDL (source) against live target database definitions.")

# ---------------------------------------------------------------------------
# Header: GitLab source + Target connection
# ---------------------------------------------------------------------------
col_gl, col_tgt = st.columns(2)

with col_gl:
    st.markdown("#### Source — GitLab deployment")
    st.caption(f"{GITLAB_BASE_URL} · project {GITLAB_PROJECT_ID}")

    gitlab_token = st.text_input(
        "GitLab personal access token",
        type="password",
        key="sch_gitlab_token",
        help="Required scopes: read_api, read_repository",
    )

    _apply_pending_branch()

    branch_col, refresh_col = st.columns([3, 1])
    with refresh_col:
        st.write("")
        st.write("")
        load_branches_clicked = st.button("Load branches", key="sch_load_branches")
    with branch_col:
        if load_branches_clicked:
            cfg = make_gitlab_config(gitlab_token)
            if not cfg:
                st.error("Enter your GitLab PAT first.")
            else:
                with st.spinner("Loading branches…"):
                    out = GitLabClient(cfg).list_branches()
                if out.ok:
                    st.session_state.sch_branch_list = out.data or []
                    if st.session_state.sch_branch_list and st.session_state.get("sch_branch") not in st.session_state.sch_branch_list:
                        st.session_state.sch_branch = st.session_state.sch_branch_list[0]
                    st.success(f"Loaded {len(st.session_state.sch_branch_list)} branch(es).")
                else:
                    st.error(out.error)

        branch_options = st.session_state.sch_branch_list or ["main"]
        branch = st.selectbox("Branch", options=branch_options, key="sch_branch")

    gl_client: GitLabClient | None = None
    if gitlab_token.strip():
        cfg = make_gitlab_config(gitlab_token, branch)
        if cfg:
            gl_client = GitLabClient(cfg)

    db_options: list[str] = []
    if gl_client:
        db_out = gl_client.list_db_folders(branch)
        if db_out.ok:
            db_options = db_out.data or []
        elif gitlab_token.strip():
            st.warning(db_out.error)
    elif gitlab_token.strip():
        st.caption("Click **Load branches** to connect to GitLab.")
    else:
        st.caption("Enter PAT and load branches to browse deployments.")

    database = st.selectbox("Database folder", options=db_options or [""], key="sch_database")
    server_options: list[str] = []
    if gl_client and database:
        srv_out = gl_client.list_server_folders(database, branch)
        if srv_out.ok:
            server_options = srv_out.data or []
        else:
            st.warning(srv_out.error)
    server_folder = st.selectbox("Server folder", options=server_options or [""], key="sch_server")

    if st.button("Load deployment", key="sch_load"):
        if not gitlab_token.strip():
            st.error("Enter your GitLab PAT.")
        elif not gl_client:
            st.error("Could not connect to GitLab — check your PAT.")
        elif not database or not server_folder:
            st.error("Select database and server folder.")
        else:
            filenames = list(OBJECT_TYPE_FILES.values())
            out = gl_client.fetch_deployment_files(database, server_folder, branch, filenames)
            if not out.ok:
                st.error(out.error)
            else:
                payload = out.data or {}
                st.session_state.sch_deployment_files = payload.get("files", {})
                st.session_state.sch_missing_files = payload.get("missing", [])
                st.session_state.sch_bundle_path = payload.get("bundle_path", "")
                info = gl_client.fetch_migration_info(database, server_folder, branch)
                if info.ok and info.data:
                    mig = info.data
                    mig_branch = str(mig.get("branch", "") or "").strip()
                    if mig_branch:
                        st.session_state.sch_pending_branch = mig_branch
                    if mig.get("target_database"):
                        st.session_state.sch_az_database = mig["target_database"]
                    if mig.get("target_server"):
                        st.session_state.sch_az_server = mig["target_server"]
                st.success(
                    f"Loaded {len(st.session_state.sch_deployment_files)} file(s) from "
                    f"`{st.session_state.sch_bundle_path}`."
                )
                if st.session_state.get("sch_pending_branch"):
                    st.rerun()

    if st.session_state.sch_bundle_path:
        st.caption(f"Bundle: `{st.session_state.sch_bundle_path}`")
    if st.session_state.sch_missing_files:
        st.caption(f"Missing in repo: {', '.join(st.session_state.sch_missing_files)}")

with col_tgt:
    st.markdown("#### Target — SQL Server / Azure SQL")
    az_server = st.text_input("Server", key="sch_az_server")
    az_database = st.text_input("Database", key="sch_az_database")
    az_auth = st.radio(
        "Authentication",
        options=list(AUTH_METHOD_LABELS.keys()),
        format_func=lambda k: AUTH_METHOD_LABELS[k],
        key="sch_az_auth",
    )
    az_trust_cert = st.checkbox("Trust server certificate", value=True, key="sch_az_trust_cert")
    az_email = ""
    if az_auth == "azure_ad_interactive":
        az_email = st.text_input("Email (UPN)", key="sch_az_email")

    if st.button("Test Target connection", key="sch_test_az"):
        if not all([az_server, az_database]):
            st.error("Fill Server and Database.")
        elif az_auth == "azure_ad_interactive" and not az_email:
            st.error("Email required for Azure AD sign-in.")
        else:
            conn = AzureConnection(
                server=az_server,
                database=az_database,
                email=az_email,
                auth_method=az_auth,
                trust_server_certificate=az_trust_cert,
            )
            out = test_azure(conn)
            if out.ok:
                st.success("Target connection OK.")
            else:
                st.error(out.error)

# ---------------------------------------------------------------------------
# Compare action
# ---------------------------------------------------------------------------
search = st.text_input("Search objects", key="sch_search", placeholder="Filter by name, schema, table…")
view_filter = st.radio(
    "Show",
    ["All", "Differences only", "Missing in DB"],
    horizontal=True,
    key="sch_view_filter",
)

compare_clicked = st.button("Compare all", type="primary", key="sch_compare_all")

if compare_clicked:
    if not st.session_state.sch_deployment_files:
        st.error("Load deployment from GitLab first.")
    elif not all([az_server, az_database]):
        st.error("Target Server and Database are required.")
    elif az_auth == "azure_ad_interactive" and not (az_email or st.session_state.get("sch_az_email")):
        st.error("Email (UPN) required for Azure AD sign-in.")
    else:
        progress = st.progress(0.0, text="Parsing GitLab deployment files…")
        gitlab_objects = parse_all_deployment_files(st.session_state.sch_deployment_files)
        progress.progress(0.35, text="Fetching live database definitions…")
        azure_conn = AzureConnection(
            server=az_server.strip(),
            database=az_database.strip(),
            email=(az_email or st.session_state.get("sch_az_email") or "").strip(),
            auth_method=az_auth,
            trust_server_certificate=az_trust_cert,
        )
        types = list(OBJECT_TYPE_FILES.keys())
        db_objects, fetch_err = fetch_all_objects(azure_conn, types)
        progress.progress(0.75, text="Building comparison…")
        compare_result = run_schema_compare(gitlab_objects, db_objects)
        compare_result.missing_files = list(st.session_state.sch_missing_files)
        compare_result.bundle_path = st.session_state.sch_bundle_path
        st.session_state.sch_compare_result = compare_result
        progress.progress(1.0, text="Done")
        progress.empty()
        if fetch_err:
            st.warning(f"Partial DB fetch issues: {fetch_err}")
        st.success("Schema comparison complete.")
        st.rerun()

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
raw_result = st.session_state.sch_compare_result
if raw_result is None:
    st.info("Load a GitLab deployment, connect to the target database, then click **Compare all**.")
    st.stop()

result = filter_results(raw_result, view_filter, search)
summary = result.summary

m1, m2, m3, m4 = st.columns(4)
m1.metric("Identical", summary.identical)
m2.metric("Different", summary.different)
m3.metric("Only in GitLab", summary.only_gitlab)
m4.metric("Only in DB", summary.only_db)

skipped_types: list[str] = []
for object_type in OBJECT_TYPE_FILES:
    filename = OBJECT_TYPE_FILES[object_type]
    items = raw_result.by_type.get(object_type, [])
    if filename in raw_result.missing_files and not items:
        skipped_types.append(_TYPE_LABELS.get(object_type, object_type))
if skipped_types:
    st.caption(
        "Skipped (not in deployment, none in DB): "
        + ", ".join(skipped_types)
    )

st.divider()

with st.container(border=True, key="sch_objects_pane", height=520):
    st.subheader("Objects by type")

    for object_type in OBJECT_TYPE_FILES:
        filename = OBJECT_TYPE_FILES[object_type]
        label = _TYPE_LABELS.get(object_type, object_type)
        items = result.by_type.get(object_type, [])

        if filename in result.missing_files and not items:
            continue

        header = f"{label} ({filename}) — {_type_summary(items)}"
        with st.expander(header, expanded=object_type in ("CONSTRAINT", "TABLE") and bool(items)):
            if not items:
                st.caption("No objects.")
                continue
            rows = []
            for item in items:
                rows.append(
                    {
                        "Status": f"{_STATUS_ICON.get(item.status, '?')} {item.status}",
                        "Owner": item.schema,
                        "Object": item.name,
                        "Parent": item.parent,
                        "Line": item.gitlab_line or "",
                        "Key": item.object_key,
                    }
                )
            df = pd.DataFrame(rows)
            event = st.dataframe(
                df.drop(columns=["Key"]),
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key=f"sch_df_{object_type}",
            )
            sel = event.selection
            if sel and sel.rows:
                idx = sel.rows[0]
                st.session_state.sch_selected_object_key = df.iloc[idx]["Key"]
                st.session_state.sch_selected_object_type = object_type

selected = _resolve_selected(result)

if selected:
    bottom = _get_bottom_container()
    if bottom is not None:
        with bottom:
            _render_ddl_pane(selected)
    else:
        st.markdown('<div class="sch-ddl-open-marker"></div>', unsafe_allow_html=True)
        with st.container(border=True, key="sch_ddl_pane"):
            _render_ddl_pane(selected)
