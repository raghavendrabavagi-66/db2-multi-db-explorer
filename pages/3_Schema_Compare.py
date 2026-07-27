"""Schema Compare — GitLab deployment DDL vs live target database."""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit.components.v1 as components

import pandas as pd
import streamlit as st

from azure_client import AUTH_METHOD_LABELS, AzureConnection, test_connection as test_azure
from azure_ddl_fetcher import fetch_all_objects, fetch_constraints, fetch_indexes
from constraint_sync import (
    apply_sync_script,
    generate_batch_scripts,
    generate_sync_script,
    preflight_constraint,
)
from index_sync import (
    apply_index_sync_script,
    generate_index_batch_scripts,
    generate_index_sync_script,
    preflight_index,
)
from deployment_parser import OBJECT_TYPE_FILES, parse_all_deployment_files, parse_deployment_file
from gitlab_client import (
    GITLAB_BASE_URL,
    GITLAB_PROJECT_ID,
    GitLabClient,
    make_gitlab_config,
)
from constraint_summary import fk_summary_table
from index_summary import index_summary_table
from diff_viewer import prepare_display_ddl, side_by_side_diff_html
from schema_compare_engine import (
    ObjectCompareResult,
    filter_results,
    merge_type_results,
    refresh_type_compare,
    run_schema_compare,
)

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
    obj_type = st.session_state.get("sch_selected_object_type", "")
    if not key:
        return None
    if obj_type:
        for item in result.by_type.get(obj_type, []):
            if item.object_key == key:
                return item
    for items in result.by_type.values():
        for item in items:
            if item.object_key == key:
                return item
    return None


def _azure_conn_from_session() -> AzureConnection | None:
    stored = st.session_state.get("sch_azure_conn")
    if stored is not None:
        return stored
    server = st.session_state.get("sch_az_server", "").strip()
    database = st.session_state.get("sch_az_database", "").strip()
    if not server or not database:
        return None
    auth = st.session_state.get("sch_az_auth", "azure_ad_interactive")
    return AzureConnection(
        server=server,
        database=database,
        auth_method=auth,
        trust_server_certificate=st.session_state.get("sch_az_trust_cert", True),
    )


def _append_apply_log(object_key: str, action: str, ok: bool, error: str = "") -> None:
    entry = {
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "object_key": object_key,
        "action": action,
        "ok": ok,
        "error": error,
    }
    log = list(st.session_state.get("sch_apply_log", []))
    log.insert(0, entry)
    st.session_state.sch_apply_log = log[:50]


def _refresh_constraints_compare() -> None:
    """Re-fetch CONSTRAINT objects and patch compare result."""
    conn = _azure_conn_from_session()
    compare_result = st.session_state.get("sch_compare_result")
    if conn is None or compare_result is None:
        return
    db_map = fetch_constraints(conn)
    content = st.session_state.sch_deployment_files.get("04_constraints.sql", "")
    gl_list = parse_deployment_file(content, "04_constraints.sql")
    type_results = refresh_type_compare(
        {"CONSTRAINT": gl_list},
        {"CONSTRAINT": db_map},
        "CONSTRAINT",
    )
    merge_type_results(compare_result, "CONSTRAINT", type_results)


def _refresh_indexes_compare() -> None:
    """Re-fetch INDEX objects and patch compare result."""
    conn = _azure_conn_from_session()
    compare_result = st.session_state.get("sch_compare_result")
    if conn is None or compare_result is None:
        return
    db_map = fetch_indexes(conn)
    content = st.session_state.sch_deployment_files.get("05_index.sql", "")
    gl_list = parse_deployment_file(content, "05_index.sql")
    type_results = refresh_type_compare(
        {"INDEX": gl_list},
        {"INDEX": db_map},
        "INDEX",
    )
    merge_type_results(compare_result, "INDEX", type_results)


def _render_constraint_sync(selected: ObjectCompareResult) -> None:
    """Sync script preview and apply controls for constraints."""
    script = generate_sync_script(selected)
    conn = _azure_conn_from_session()
    db_name = conn.database if conn else st.session_state.get("sch_az_database", "target")

    if selected.status == "only_db":
        st.markdown("**Suggested DROP script** (read-only — not applied from GitLab sync)")
        if script.steps:
            st.code(script.sql_text, language="sql")
        else:
            st.caption(script.message or "No drop script available.")
        return

    if script.action not in ("create", "replace"):
        st.info(script.message or "No sync action available for this object.")
        return

    with st.expander("Sync script (GitLab → database)", expanded=True):
        st.code(script.sql_text, language="sql")

    if script.warnings:
        for warning in script.warnings:
            st.warning(warning)

    if conn is None:
        st.error("Target connection not available. Run **Compare all** first.")
        return

    preflight = preflight_constraint(conn, selected, script)
    for blocker in preflight.blockers:
        st.error(blocker)
    for warning in preflight.warnings:
        if warning not in script.warnings:
            st.warning(warning)

    confirm_key = f"sch_sync_confirm_{selected.object_key}"
    confirmed = st.checkbox(
        f"I confirm applying this change to **{db_name}**",
        key=confirm_key,
    )

    apply_col, _ = st.columns([1, 3])
    with apply_col:
        apply_disabled = not confirmed or not preflight.ok
        if st.button(
            "Apply to database",
            type="primary",
            key=f"sch_apply_{selected.object_key}",
            disabled=apply_disabled,
        ):
            with st.spinner("Applying constraint sync…"):
                outcome = apply_sync_script(conn, script)
            if outcome.ok:
                _append_apply_log(selected.object_key, script.action, True)
                _refresh_constraints_compare()
                st.success("Constraint applied successfully.")
                st.rerun()
            else:
                _append_apply_log(selected.object_key, script.action, False, outcome.error)
                st.error(outcome.error)


def _index_drift_items(items: list[ObjectCompareResult]) -> list[ObjectCompareResult]:
    return [i for i in items if i.status in ("different", "only_gitlab")]


def _render_index_sync(selected: ObjectCompareResult) -> None:
    """Sync script preview and apply controls for indexes."""
    script = generate_index_sync_script(selected)
    conn = _azure_conn_from_session()
    db_name = conn.database if conn else st.session_state.get("sch_az_database", "target")

    if selected.status == "only_db":
        st.markdown("**Suggested DROP script** (read-only — not applied from GitLab sync)")
        if script.steps:
            st.code(script.sql_text, language="sql")
        else:
            st.caption(script.message or "No drop script available.")
        return

    if script.action not in ("create", "replace"):
        st.info(script.message or "No sync action available for this object.")
        return

    with st.expander("Sync script (GitLab → database)", expanded=True):
        st.code(script.sql_text, language="sql")

    if script.warnings:
        for warning in script.warnings:
            st.warning(warning)

    if conn is None:
        st.error("Target connection not available. Run **Compare all** first.")
        return

    preflight = preflight_index(conn, selected, script)
    for blocker in preflight.blockers:
        st.error(blocker)
    for warning in preflight.warnings:
        if warning not in script.warnings:
            st.warning(warning)

    confirm_key = f"sch_index_sync_confirm_{selected.object_key}"
    confirmed = st.checkbox(
        f"I confirm applying this change to **{db_name}**",
        key=confirm_key,
    )

    apply_col, _ = st.columns([1, 3])
    with apply_col:
        apply_disabled = not confirmed or not preflight.ok
        if st.button(
            "Apply to database",
            type="primary",
            key=f"sch_index_apply_{selected.object_key}",
            disabled=apply_disabled,
        ):
            with st.spinner("Applying index sync…"):
                outcome = apply_index_sync_script(conn, script)
            if outcome.ok:
                _append_apply_log(selected.object_key, script.action, True)
                _refresh_indexes_compare()
                st.success("Index applied successfully.")
                st.rerun()
            else:
                _append_apply_log(selected.object_key, script.action, False, outcome.error)
                st.error(outcome.error)


def _constraint_drift_items(items: list[ObjectCompareResult]) -> list[ObjectCompareResult]:
    return [i for i in items if i.status in ("different", "only_gitlab")]


def _render_constraint_batch_sync(all_items: list[ObjectCompareResult]) -> None:
    """Batch preview and apply for constraint drift."""
    drift = _constraint_drift_items(all_items)
    if not drift:
        return

    conn = _azure_conn_from_session()
    db_name = conn.database if conn else st.session_state.get("sch_az_database", "target")
    batch_pairs = generate_batch_scripts(all_items)

    st.markdown(f"**Constraint sync** — {len(drift)} object(s) with drift")
    preview_key = "sch_batch_preview_open"
    if st.button(f"Preview batch sync ({len(batch_pairs)} scripts)", key="sch_batch_preview_btn"):
        st.session_state[preview_key] = not st.session_state.get(preview_key, False)

    if st.session_state.get(preview_key):
        for idx, (item, script) in enumerate(batch_pairs, start=1):
            st.caption(
                f"{idx}. `{item.schema}.{item.name}` on `{item.parent}` "
                f"({item.status}, {script.action})"
            )
            st.code(script.sql_text, language="sql")

    if conn is None:
        st.caption("Run **Compare all** to enable batch apply.")
        return

    batch_confirm_key = "sch_batch_confirm"
    batch_confirmed = st.checkbox(
        f"I confirm applying **{len(batch_pairs)}** constraint change(s) to **{db_name}**",
        key=batch_confirm_key,
    )
    if st.button(
        f"Apply all constraint drifts ({len(batch_pairs)})",
        type="primary",
        key="sch_batch_apply",
        disabled=not batch_confirmed or not batch_pairs,
    ):
        results: list[dict[str, str]] = []
        failed = False
        with st.spinner("Applying batch constraint sync…"):
            for item, script in batch_pairs:
                preflight = preflight_constraint(conn, item, script)
                if not preflight.ok:
                    results.append(
                        {
                            "Object": item.name,
                            "Table": item.parent,
                            "Result": "blocked",
                            "Detail": "; ".join(preflight.blockers),
                        }
                    )
                    failed = True
                    break
                outcome = apply_sync_script(conn, script)
                if outcome.ok:
                    _append_apply_log(item.object_key, f"batch:{script.action}", True)
                    results.append(
                        {
                            "Object": item.name,
                            "Table": item.parent,
                            "Result": "ok",
                            "Detail": "",
                        }
                    )
                else:
                    _append_apply_log(item.object_key, f"batch:{script.action}", False, outcome.error)
                    results.append(
                        {
                            "Object": item.name,
                            "Table": item.parent,
                            "Result": "error",
                            "Detail": outcome.error,
                        }
                    )
                    failed = True
                    break
        _refresh_constraints_compare()
        st.session_state["sch_batch_apply_results"] = results
        if failed:
            st.error("Batch apply stopped on first failure. Earlier objects in the batch were committed.")
        else:
            st.success(f"Applied {len(results)} constraint change(s).")
        st.session_state[preview_key] = False
        st.rerun()

    batch_results = st.session_state.get("sch_batch_apply_results")
    if batch_results:
        st.dataframe(pd.DataFrame(batch_results), width="stretch", hide_index=True)


def _render_index_batch_sync(all_items: list[ObjectCompareResult]) -> None:
    """Batch preview and apply for index drift."""
    drift = _index_drift_items(all_items)
    if not drift:
        return

    conn = _azure_conn_from_session()
    db_name = conn.database if conn else st.session_state.get("sch_az_database", "target")
    batch_pairs = generate_index_batch_scripts(all_items)

    st.markdown(f"**Index sync** — {len(drift)} object(s) with drift")
    preview_key = "sch_index_batch_preview_open"
    if st.button(f"Preview batch sync ({len(batch_pairs)} scripts)", key="sch_index_batch_preview_btn"):
        st.session_state[preview_key] = not st.session_state.get(preview_key, False)

    if st.session_state.get(preview_key):
        for idx, (item, script) in enumerate(batch_pairs, start=1):
            st.caption(
                f"{idx}. `{item.schema}.{item.name}` on `{item.parent}` "
                f"({item.status}, {script.action})"
            )
            st.code(script.sql_text, language="sql")

    if conn is None:
        st.caption("Run **Compare all** to enable batch apply.")
        return

    batch_confirm_key = "sch_index_batch_confirm"
    batch_confirmed = st.checkbox(
        f"I confirm applying **{len(batch_pairs)}** index change(s) to **{db_name}**",
        key=batch_confirm_key,
    )
    if st.button(
        f"Apply all index drifts ({len(batch_pairs)})",
        type="primary",
        key="sch_index_batch_apply",
        disabled=not batch_confirmed or not batch_pairs,
    ):
        results: list[dict[str, str]] = []
        failed = False
        with st.spinner("Applying batch index sync…"):
            for item, script in batch_pairs:
                preflight = preflight_index(conn, item, script)
                if not preflight.ok:
                    results.append(
                        {
                            "Object": item.name,
                            "Table": item.parent,
                            "Result": "blocked",
                            "Detail": "; ".join(preflight.blockers),
                        }
                    )
                    failed = True
                    break
                outcome = apply_index_sync_script(conn, script)
                if outcome.ok:
                    _append_apply_log(item.object_key, f"batch:{script.action}", True)
                    results.append(
                        {
                            "Object": item.name,
                            "Table": item.parent,
                            "Result": "ok",
                            "Detail": "",
                        }
                    )
                else:
                    _append_apply_log(item.object_key, f"batch:{script.action}", False, outcome.error)
                    results.append(
                        {
                            "Object": item.name,
                            "Table": item.parent,
                            "Result": "error",
                            "Detail": outcome.error,
                        }
                    )
                    failed = True
                    break
        _refresh_indexes_compare()
        st.session_state["sch_index_batch_apply_results"] = results
        if failed:
            st.error("Batch apply stopped on first failure. Earlier objects in the batch were committed.")
        else:
            st.success(f"Applied {len(results)} index change(s).")
        st.session_state[preview_key] = False
        st.rerun()

    batch_results = st.session_state.get("sch_index_batch_apply_results")
    if batch_results:
        st.dataframe(pd.DataFrame(batch_results), width="stretch", hide_index=True)


def _render_ddl_pane(selected: ObjectCompareResult) -> None:
    st.subheader("DDL comparison")
    if selected.source_file:
        src_file = selected.source_file
    elif selected.status in ("identical", "different", "only_gitlab"):
        src_file = OBJECT_TYPE_FILES.get(selected.object_type, "—")
    else:
        src_file = "—"
    line_info = f" · line {selected.gitlab_line}" if selected.gitlab_line else ""
    type_label = _TYPE_LABELS.get(selected.object_type, selected.object_type)
    st.caption(
        f"**{type_label}** · `{selected.schema}.{selected.name}`"
        + (f" on `{selected.parent}`" if selected.parent else "")
        + f" · {src_file}{line_info}"
        + f" · status: **{selected.status}**"
    )
    tab_sql, tab_summary, tab_sync = st.tabs(["SQL view", "Summary view", "Sync"])
    with tab_sql:
        diff_html = side_by_side_diff_html(selected.gitlab_ddl, selected.db_ddl)
        if not prepare_display_ddl(selected.gitlab_ddl) and selected.gitlab_ddl.strip():
            st.warning("GitLab DDL did not render in the diff — showing raw SQL below.")
            st.code(selected.gitlab_ddl, language="sql")
        elif not selected.gitlab_ddl.strip() and selected.status == "different":
            st.warning("GitLab DDL is empty in the comparison result — re-run **Compare all** after loading deployment.")
        elif not selected.gitlab_ddl.strip() and selected.status == "only_db":
            if selected.object_type == "TABLE":
                st.warning("Object exists in the database but was not found in GitLab **03_table.sql**.")
            elif selected.object_type.startswith("MQT"):
                st.info(
                    "No GitLab MQT DDL for this object. "
                    "**Regular tables** such as CRIT_DEFN belong under **Tables (03_table.sql)** — not MQT Deferred."
                )
            else:
                st.warning(
                    f"Object exists in the database but was not found in GitLab "
                    f"**{OBJECT_TYPE_FILES.get(selected.object_type, 'deployment files')}**."
                )
        components.html(diff_html, height=_DDL_IFRAME_HEIGHT, scrolling=False)
    with tab_summary:
        st.table(
            {
                "Property": ["Status", "Object type", "Schema", "Name", "Parent table", "Source file", "GitLab line"],
                "Value": [
                    selected.status,
                    _TYPE_LABELS.get(selected.object_type, selected.object_type),
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
                width="stretch",
                hide_index=True,
                column_config={
                    "Match": st.column_config.TextColumn(width="small"),
                },
            )
            mismatches = [r for r in fk_rows if r["Match"] == "no"]
            if mismatches:
                props = ", ".join(r["Property"] for r in mismatches)
                st.warning(f"Mismatch: {props}")
        index_rows = index_summary_table(selected.gitlab_ddl, selected.db_ddl)
        if index_rows:
            st.markdown("**Index properties**")
            index_df = pd.DataFrame(index_rows)
            st.dataframe(
                index_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "Match": st.column_config.TextColumn(width="small"),
                },
            )
            index_mismatches = [r for r in index_rows if r["Match"] == "no"]
            if index_mismatches:
                props = ", ".join(r["Property"].strip() for r in index_mismatches)
                st.warning(f"Mismatch: {props}")
        if selected.status == "different":
            st.warning("Definitions differ after normalization — review inline highlights in SQL view.")
        elif selected.status == "identical":
            st.success("Definitions match.")
        elif selected.status == "only_gitlab":
            st.warning("Object exists in GitLab deployment but was not found in the target database.")
        else:
            st.warning("Object exists in the database but is not in the GitLab deployment files.")

    with tab_sync:
        if selected.object_type == "CONSTRAINT":
            _render_constraint_sync(selected)
        elif selected.object_type == "INDEX":
            _render_index_sync(selected)
        else:
            st.info("Apply from GitLab is available for **Constraints** and **Indexes**.")


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
if "sch_azure_conn" not in st.session_state:
    st.session_state.sch_azure_conn = None
if "sch_apply_log" not in st.session_state:
    st.session_state.sch_apply_log = []

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
                st.session_state.sch_compare_result = None
                st.session_state.sch_selected_object_key = ""
                st.session_state.sch_selected_object_type = ""
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
    if az_auth == "azure_ad_interactive":
        st.caption("A browser window opens for Microsoft sign-in (account picker / MFA).")

    if st.button("Test Target connection", key="sch_test_az"):
        if not all([az_server, az_database]):
            st.error("Fill Server and Database.")
        else:
            conn = AzureConnection(
                server=az_server,
                database=az_database,
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
    else:
        progress = st.progress(0.0, text="Parsing GitLab deployment files…")
        gitlab_objects = parse_all_deployment_files(st.session_state.sch_deployment_files)
        progress.progress(0.35, text="Fetching live database definitions…")
        azure_conn = AzureConnection(
            server=az_server.strip(),
            database=az_database.strip(),
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
        st.session_state.sch_azure_conn = azure_conn
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
            if object_type == "CONSTRAINT":
                _render_constraint_batch_sync(raw_result.by_type.get("CONSTRAINT", []))
            if object_type == "INDEX":
                _render_index_batch_sync(raw_result.by_type.get("INDEX", []))
            rows = []
            for item in items:
                rows.append(
                    {
                        "Status": f"{_STATUS_ICON.get(item.status, '?')} {item.status}",
                        "Owner": item.schema,
                        "Object": item.name,
                        "Parent": item.parent,
                        "Line": str(item.gitlab_line) if item.gitlab_line is not None else "—",
                        "Key": item.object_key,
                    }
                )
            df = pd.DataFrame(rows)
            event = st.dataframe(
                df.drop(columns=["Key"]),
                width="stretch",
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
