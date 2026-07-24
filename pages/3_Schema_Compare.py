"""Schema Compare — GitLab deployment DDL vs live target database."""

from __future__ import annotations

import streamlit.components.v1 as components

import pandas as pd
import streamlit as st

from azure_client import AUTH_METHOD_LABELS, AzureConnection, test_connection as test_azure
from azure_ddl_fetcher import fetch_all_objects
from deployment_parser import OBJECT_TYPE_FILES, parse_all_deployment_files
from gitlab_client import GitLabClient, load_gitlab_config
from schema_compare_engine import ObjectCompareResult, filter_results, run_schema_compare

st.set_page_config(page_title="Schema Compare", layout="wide")

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

st.title("Schema Compare")
st.caption("Compare GitLab deployment DDL (source) against live target database definitions.")

gitlab_config = load_gitlab_config()
if gitlab_config is None:
    st.error(
        "GitLab is not configured. Add `[gitlab]` to `.streamlit/secrets.toml` with "
        "`base_url`, `project_id`, and `token` (or set GITLAB_* environment variables)."
    )
    st.stop()

gl_client = GitLabClient(gitlab_config)

# ---------------------------------------------------------------------------
# Header: GitLab source + Target connection
# ---------------------------------------------------------------------------
col_gl, col_tgt = st.columns(2)

with col_gl:
    st.markdown("#### Source — GitLab deployment")
    st.caption(f"{gitlab_config.base_url} · project {gitlab_config.project_id}")
    branch = st.text_input("Branch", value=gitlab_config.default_branch, key="sch_branch")

    db_out = gl_client.list_db_folders(branch)
    db_options = db_out.data if db_out.ok else []
    if not db_out.ok:
        st.warning(db_out.error)

    database = st.selectbox("Database folder", options=db_options or [""], key="sch_database")
    server_options: list[str] = []
    if database:
        srv_out = gl_client.list_server_folders(database, branch)
        if srv_out.ok:
            server_options = srv_out.data or []
        else:
            st.warning(srv_out.error)
    server_folder = st.selectbox("Server folder", options=server_options or [""], key="sch_server")

    if st.button("Load deployment", key="sch_load"):
        if not database or not server_folder:
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
                    if mig.get("branch"):
                        st.session_state.sch_branch = mig["branch"]
                    if mig.get("target_database"):
                        st.session_state.sch_az_database = mig["target_database"]
                    if mig.get("target_server"):
                        st.session_state.sch_az_server = mig["target_server"]
                st.success(
                    f"Loaded {len(st.session_state.sch_deployment_files)} file(s) from "
                    f"`{st.session_state.sch_bundle_path}`."
                )

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

st.divider()
st.subheader("Objects by type")

selected: ObjectCompareResult | None = None

for object_type in OBJECT_TYPE_FILES:
    filename = OBJECT_TYPE_FILES[object_type]
    label = _TYPE_LABELS.get(object_type, object_type)
    items = result.by_type.get(object_type, [])

    if filename in result.missing_files and not items:
        with st.expander(f"{label} ({filename}) — file not found in repo"):
            st.caption("This deployment file is not present in the GitLab bundle.")
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
            key = df.iloc[idx]["Key"]
            st.session_state.sch_selected_object_key = key
            st.session_state.sch_selected_object_type = object_type
            selected = items[idx]

# Resolve selected object across reruns
if not selected and st.session_state.sch_selected_object_key:
    for object_type, items in result.by_type.items():
        for item in items:
            if item.object_key == st.session_state.sch_selected_object_key:
                selected = item
                st.session_state.sch_selected_object_type = object_type
                break

if selected:
    st.divider()
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
        components.html(selected.diff_html, height=480, scrolling=True)
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
        if selected.status == "different":
            st.warning("Definitions differ after normalization — review highlighted lines in SQL view.")
        elif selected.status == "identical":
            st.success("Definitions match.")
        elif selected.status == "only_gitlab":
            st.warning("Object exists in GitLab deployment but was not found in the target database.")
        else:
            st.warning("Object exists in the database but is not in the GitLab deployment files.")
