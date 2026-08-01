"""Row Compare — DB2 vs Azure SQL table row-count comparison (Studio Precision UI)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from db2_explorer.clients.azure import AUTH_METHOD_LABELS, AzureConnection, test_connection as test_azure
from db2_explorer.clients.db2 import query_single
from db2_explorer.compare.row_compare import (
    CompareResult,
    comparison_metrics,
    filter_comparison,
    list_source_tables,
    run_comparison,
)
from db2_explorer.data.connections import Connection, parse_jdbc_db2_url
from db2_explorer.ui.stitch_shell import (
    render_html,
    row_setup_header_html,
    row_setup_source_header_html,
    row_setup_target_header_html,
    row_toolbar_html,
    workspace_nav,
)
from db2_explorer.ui.theme import apply_page

apply_page(title="Row Compare", layout="wide")


def _table_checkbox_key(table_name: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in table_name)
    return f"cmp_tbl_{safe}"


def _selected_tables_from_checkboxes(tables: list[str]) -> list[str]:
    return [t for t in tables if st.session_state.get(_table_checkbox_key(t), False)]


def _set_all_table_checks(tables: list[str], checked: bool) -> None:
    for t in tables:
        st.session_state[_table_checkbox_key(t)] = checked


def _split_tables_into_columns(tables: list[str], num_cols: int) -> list[list[str]]:
    if not tables:
        return [[] for _ in range(num_cols)]
    cols: list[list[str]] = [[] for _ in range(num_cols)]
    per_col = (len(tables) + num_cols - 1) // num_cols
    for i, name in enumerate(tables):
        col_idx = min(i // per_col, num_cols - 1)
        cols[col_idx].append(name)
    return cols


@st.dialog("Compare Connection Setup", width="large")
def _connection_setup_dialog() -> None:
    """Redgate-style dual-column setup — stitch screen 01."""
    render_html(row_setup_header_html())
    src_col, tgt_col = st.columns(2)
    with src_col:
        render_html(row_setup_source_header_html())
        st.text_input("Database Name", key="cmp_db2_database")
        h_col, p_col = st.columns([2, 1])
        with h_col:
            st.text_input("Host", key="cmp_db2_host")
        with p_col:
            st.number_input("Port", min_value=1, max_value=65535, value=50000, key="cmp_db2_port")
        st.text_input("Username", key="cmp_db2_user")
        st.text_input("Password", type="password", key="cmp_db2_password")
        with st.expander("Paste JDBC URL"):
            jdbc_in = st.text_input(
                "jdbc:db2://host:port/database",
                key="cmp_db2_jdbc",
                placeholder="jdbc:db2://ss-db22d:50000/infoq",
            )
            if st.button("Apply JDBC", key="cmp_apply_jdbc"):
                parsed = parse_jdbc_db2_url(jdbc_in)
                if parsed:
                    dbname, host, port = parsed
                    st.session_state.cmp_db2_database = dbname
                    st.session_state.cmp_db2_host = host
                    st.session_state.cmp_db2_port = port
                    st.rerun()
                else:
                    st.warning("Could not parse JDBC URL.")
        if st.button("Test Connection", key="cmp_test_db2", use_container_width=True):
            db2_database = st.session_state.cmp_db2_database
            db2_host = st.session_state.cmp_db2_host
            db2_user = st.session_state.cmp_db2_user
            db2_password = st.session_state.cmp_db2_password
            db2_port = st.session_state.cmp_db2_port
            if not all([db2_database, db2_host, db2_user, db2_password]):
                st.error("Fill Database, Host, Username, and Password.")
            else:
                conn = Connection(dbname=db2_database, host=db2_host, port=int(db2_port))
                out = query_single(conn, db2_user, db2_password, "SELECT 1 AS OK FROM SYSIBM.SYSDUMMY1")
                st.success("DB2 connection OK.") if out.ok else st.error(out.error)

    with tgt_col:
        render_html(row_setup_target_header_html())
        st.text_input("Azure SQL Server", key="cmp_az_server",
                      placeholder="az-db-prod-sql.database.windows.net")
        st.radio(
            "Authentication",
            options=list(AUTH_METHOD_LABELS.keys()),
            format_func=lambda k: AUTH_METHOD_LABELS[k],
            key="cmp_az_auth",
        )
        st.checkbox("Trust server certificate", value=True, key="cmp_az_trust_cert")
        st.text_input("Database Name", key="cmp_az_database")
        st.radio(
            "Target table naming",
            options=["original", "staging"],
            format_func=lambda v: (
                "Original — source `table1` ↔ target `table1`"
                if v == "original"
                else "Staging — source `table1` ↔ target `table1_staging`"
            ),
            key="cmp_target_table_mode",
        )
        if st.button("Test Connection", key="cmp_test_az", use_container_width=True):
            az_server = st.session_state.cmp_az_server
            az_database = st.session_state.cmp_az_database
            az_auth = st.session_state.cmp_az_auth
            if not all([az_server, az_database]):
                st.error("Fill Server and Database.")
            else:
                az_conn = AzureConnection(
                    server=az_server,
                    database=az_database,
                    auth_method=az_auth,
                    trust_server_certificate=st.session_state.cmp_az_trust_cert,
                )
                out = test_azure(az_conn)
                st.success("Target connection OK.") if out.ok else st.error(out.error)

    st.markdown("---")
    map_col1, map_mid, map_col2 = st.columns([2, 1, 2])
    with map_col1:
        st.text_input("Source schema", value="USERID", key="cmp_db2_schema")
    with map_mid:
        st.markdown("<p style='text-align:center;padding-top:1.75rem;color:#505f76;'>maps to</p>",
                    unsafe_allow_html=True)
    with map_col2:
        st.text_input("Target schema", value="dbo", key="cmp_azure_schema")

    if st.button("Connect & Compare →", type="primary", use_container_width=True, key="cmp_dialog_save"):
        st.session_state.rc_setup_done = True
        st.rerun()


# ── Session defaults ──
if "compare_result" not in st.session_state:
    st.session_state.compare_result = None
if "compare_ran_at" not in st.session_state:
    st.session_state.compare_ran_at = None
if "cmp_compare_scope" not in st.session_state:
    st.session_state.cmp_compare_scope = "all"
if "cmp_source_table_list" not in st.session_state:
    st.session_state.cmp_source_table_list = []
if "cmp_tables_loaded_for_schema" not in st.session_state:
    st.session_state.cmp_tables_loaded_for_schema = ""
if "cmp_table_list_columns" not in st.session_state:
    st.session_state.cmp_table_list_columns = 3
if "rc_setup_done" not in st.session_state:
    st.session_state.rc_setup_done = False

workspace_nav(
    "migrations",
    page_title="Row Compare",
    page_subtitle="DB2 vs Azure row counts",
)
render_html(row_toolbar_html())

toolbar_col1, toolbar_col2, _ = st.columns([1, 1, 4])
with toolbar_col1:
    if st.button("Edit Credentials", key="rc_edit_creds"):
        _connection_setup_dialog()
with toolbar_col2:
    config_open = st.toggle("Configuration panel", key="rc_config_open")

if not st.session_state.rc_setup_done:
    st.info("Configure source and target connections to begin.")
    if st.button("Open Connection Setup", type="primary", key="rc_open_setup"):
        _connection_setup_dialog()

with st.container(key="rc_workspace"):
    # Configuration panel — stitch screen 05
    with st.container(border=True, key="rc_config_bar"):
        cfg_left, cfg_right = st.columns([3, 1])
        with cfg_left:
            render_html(
                '<label class="text-label-caps text-secondary block mb-sm">COMPARE SCOPE</label>'
            )
            st.radio(
                "Tables to compare",
                options=["all", "selected"],
                format_func=lambda v: "Compare all tables" if v == "all" else "Selected tables only",
                key="cmp_compare_scope",
                horizontal=True,
                label_visibility="collapsed",
            )
        with cfg_right:
            st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)
            run_clicked = st.button("▶ RUN COMPARISON", type="primary", use_container_width=True, key="rc_run")

    if config_open or st.session_state.cmp_compare_scope == "selected":
        with st.expander("Advanced table selection", expanded=st.session_state.cmp_compare_scope == "selected"):
            db2_schema = st.session_state.get("cmp_db2_schema", "USERID")
            db2_database = st.session_state.get("cmp_db2_database", "")
            db2_host = st.session_state.get("cmp_db2_host", "")
            db2_user = st.session_state.get("cmp_db2_user", "")
            db2_password = st.session_state.get("cmp_db2_password", "")
            db2_port = st.session_state.get("cmp_db2_port", 50000)

            if st.button("Load table list", key="cmp_load_tables"):
                if not all([db2_database, db2_host, db2_user, db2_password]):
                    st.error("Complete connection setup first.")
                elif not db2_schema.strip():
                    st.error("Source schema is required.")
                else:
                    load_conn = Connection(
                        dbname=db2_database.strip(),
                        host=db2_host.strip(),
                        port=int(db2_port),
                    )
                    with st.spinner("Loading tables…"):
                        names, err = list_source_tables(load_conn, db2_user, db2_password, db2_schema.strip())
                    if err:
                        st.error(err)
                    else:
                        prev = set(_selected_tables_from_checkboxes(st.session_state.cmp_source_table_list))
                        st.session_state.cmp_source_table_list = names
                        st.session_state.cmp_tables_loaded_for_schema = db2_schema.strip()
                        for t in names:
                            st.session_state[_table_checkbox_key(t)] = t in prev
                        st.success(f"Loaded {len(names)} table(s).")

            loaded = st.session_state.cmp_source_table_list
            if loaded:
                pick_toolbar = st.columns([1, 1, 2, 2])
                with pick_toolbar[0]:
                    if st.button("Select all", key="cmp_tbl_select_all"):
                        _set_all_table_checks(loaded, True)
                        st.rerun()
                with pick_toolbar[1]:
                    if st.button("Clear all", key="cmp_tbl_clear_all"):
                        _set_all_table_checks(loaded, False)
                        st.rerun()
                with pick_toolbar[2]:
                    num_cols = st.radio(
                        "Sections",
                        options=[2, 3],
                        format_func=lambda n: f"{n} columns",
                        horizontal=True,
                        key="cmp_table_list_columns",
                    )
                with pick_toolbar[3]:
                    st.caption(f"{len(_selected_tables_from_checkboxes(loaded))} of {len(loaded)} selected")
                with st.container(border=True, height=320):
                    col_chunks = _split_tables_into_columns(loaded, int(num_cols))
                    grid_cols = st.columns(int(num_cols))
                    for col_idx, grid_col in enumerate(grid_cols):
                        with grid_col:
                            for table_name in col_chunks[col_idx]:
                                st.checkbox(table_name, key=_table_checkbox_key(table_name))

    # Run comparison
    db2_database = st.session_state.get("cmp_db2_database", "")
    db2_host = st.session_state.get("cmp_db2_host", "")
    db2_user = st.session_state.get("cmp_db2_user", "")
    db2_password = st.session_state.get("cmp_db2_password", "")
    db2_port = st.session_state.get("cmp_db2_port", 50000)
    db2_schema = st.session_state.get("cmp_db2_schema", "USERID")
    azure_schema = st.session_state.get("cmp_azure_schema", "dbo")
    az_server = st.session_state.get("cmp_az_server", "")
    az_database = st.session_state.get("cmp_az_database", "")
    az_auth = st.session_state.get("cmp_az_auth", "azure_ad_interactive")
    target_table_mode = st.session_state.get("cmp_target_table_mode", "original")

    if run_clicked:
        errors = []
        if not all([db2_database, db2_host, db2_user, db2_password]):
            errors.append("DB2: Database, Host, Username, and Password are required.")
        if not all([az_server, az_database]):
            errors.append("Target: Server and Database are required.")
        if not db2_schema.strip() or not azure_schema.strip():
            errors.append("Both schema names are required.")
        if st.session_state.cmp_compare_scope == "selected":
            if not _selected_tables_from_checkboxes(st.session_state.cmp_source_table_list):
                errors.append("Select at least one table, or choose compare all.")
        if errors:
            for e in errors:
                st.error(e)
        else:
            progress = st.progress(0.0, text="Starting comparison…")
            status = st.empty()

            def _on_progress(done: int, total: int, msg: str) -> None:
                progress.progress(done / total, text=msg)
                status.caption(msg)

            db2_conn = Connection(dbname=db2_database.strip(), host=db2_host.strip(), port=int(db2_port))
            azure_conn = AzureConnection(
                server=az_server.strip(),
                database=az_database.strip(),
                auth_method=az_auth,
                trust_server_certificate=st.session_state.cmp_az_trust_cert,
            )
            with st.spinner("Running comparison…"):
                tables_arg = None
                if st.session_state.cmp_compare_scope == "selected":
                    tables_arg = _selected_tables_from_checkboxes(st.session_state.cmp_source_table_list)
                result = run_comparison(
                    db2_conn, db2_user, db2_password, db2_schema.strip(),
                    azure_conn, azure_schema.strip(),
                    target_table_mode=target_table_mode,
                    selected_tables=tables_arg,
                    on_progress=_on_progress,
                )
            progress.empty()
            status.empty()
            if result.status != "ok":
                st.error(result.error)
            else:
                st.session_state.compare_result = result
                st.session_state.compare_ran_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.cmp_view = "All"
                st.success("Comparison complete.")
                st.rerun()

    result: CompareResult | None = st.session_state.compare_result
    if result is not None and result.status == "ok" and not result.comparison.empty:
        df = result.comparison
        metrics = comparison_metrics(df)

        with st.container(key="rc_metrics"):
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total Tables", metrics["tables_source"])
            m2.metric("Matches", metrics["matched"])
            m3.metric("Mismatches", metrics["mismatched"])
            m4.metric("Failed", metrics["missing"])
            m5.metric("Rows Scanned", metrics["tables_source"])

        st.markdown("#### Comparison Details")
        view = st.radio(
            "Show",
            ["All", "Matches only", "Mismatches only", "Source only", "Target only"],
            horizontal=True,
            key="cmp_view",
        )
        view_df = filter_comparison(df, view)
        st.dataframe(
            view_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Source Count": st.column_config.NumberColumn(format="%d"),
                "Target Count": st.column_config.NumberColumn(format="%d"),
                "Delta": st.column_config.NumberColumn(format="%+d"),
            },
        )
        st.download_button(
            "Download CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="db2_azure_table_comparison.csv",
            mime="text/csv",
        )
    elif result is not None and result.status == "ok" and result.comparison.empty:
        st.warning("Comparison ran but no tables were found.")
    elif st.session_state.rc_setup_done:
        st.info("Click **RUN COMPARISON** to compare row counts.")
