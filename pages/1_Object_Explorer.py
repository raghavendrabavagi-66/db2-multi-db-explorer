"""Object Explorer — search DB2 catalog objects across many databases."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from db2_explorer.clients.db2 import DBResult, run_across_databases
from db2_explorer.data.connections import (
    CONNECTIONS_FILE,
    connections_from_rows,
    load_paths,
    parse_pasted_table,
    save_connections,
)
from db2_explorer.data.queries import MATCH_ORDER, OBJECT_TYPES
from db2_explorer.ui.components import panel_title, service_top_bar
from db2_explorer.ui.theme import apply_page

apply_page(title="Object Explorer", layout="wide", object_explorer=True)

DB_LIST_COLUMNS = ["Database", "Host", "Port"]


def _empty_db_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=DB_LIST_COLUMNS)


def _rows_to_frame(rows: list[tuple[str, str, int]]) -> pd.DataFrame:
    if not rows:
        return _empty_db_frame()
    return pd.DataFrame(rows, columns=DB_LIST_COLUMNS)


def _merge_paste_into_frame(existing: pd.DataFrame, pasted: list[tuple[str, str, int]], *, replace: bool) -> pd.DataFrame:
    new_df = _rows_to_frame(pasted)
    if replace:
        combined = new_df
    else:
        combined = pd.concat([existing, new_df], ignore_index=True)
    conns = connections_from_rows(combined.itertuples(index=False, name=None))
    return _rows_to_frame([(c.dbname, c.host, c.port) for c in conns])


def _load_saved_db_frame() -> pd.DataFrame:
    if os.path.isfile(CONNECTIONS_FILE):
        try:
            conns = load_paths([CONNECTIONS_FILE])
        except OSError:
            return _empty_db_frame()
        if conns:
            return pd.DataFrame(
                [[c.dbname, c.host, c.port] for c in conns],
                columns=DB_LIST_COLUMNS,
            )
    return _empty_db_frame()


def results_to_frame(results: list[DBResult]) -> pd.DataFrame:
    records: list[dict] = []
    for res in results:
        c = res.connection
        if res.rows:
            for row in res.rows:
                records.append(
                    {
                        "Database": c.dbname,
                        "Host": c.host,
                        "Port": c.port,
                        "Schema": row.get("Schema"),
                        "Object Name": row.get("Object Name"),
                        "Object Type": row.get("Object Type"),
                        "Sub Type": row.get("Sub Type"),
                        "Create Time": str(row.get("Create Time") or ""),
                        "Status": res.status,
                    }
                )
        else:
            records.append(
                {
                    "Database": c.dbname,
                    "Host": c.host,
                    "Port": c.port,
                    "Schema": "",
                    "Object Name": "",
                    "Object Type": "",
                    "Sub Type": "",
                    "Create Time": "",
                    "Status": res.status if not res.ok else "no matches",
                }
            )
    return pd.DataFrame.from_records(records)


if "oe_object_type" not in st.session_state:
    st.session_state.oe_object_type = OBJECT_TYPES[0]
if "results" not in st.session_state:
    st.session_state.results = None
if "last_meta" not in st.session_state:
    st.session_state.last_meta = {}
if "db_list_df" not in st.session_state:
    st.session_state.db_list_df = _load_saved_db_frame()

st.markdown('<div class="ms-oe-marker" aria-hidden="true" style="display:none;"></div>', unsafe_allow_html=True)

with st.container(key="oe_page_header"):
    service_top_bar(
        "Object Explorer",
        tagline="Multi-database catalog search",
        home_key="oe_home",
    )

connections = connections_from_rows(
    st.session_state.db_list_df.itertuples(index=False, name=None)
)

# ---------------------------------------------------------------------------
# Workspace — left 40% (connection top + fleet bottom) | right 60% (search top + results bottom)
# ---------------------------------------------------------------------------
with st.container(key="oe_workspace"):
    left_col, right_col = st.columns([4, 6], gap="medium")

    with left_col:
        with st.container(key="oe_left_column"):
            with st.container(border=True, key="oe_connection_panel"):
                panel_title("Connection")
                user_col, pass_col = st.columns(2)
                with user_col:
                    username = st.text_input("Username", key="username")
                with pass_col:
                    password = st.text_input("Password", type="password", key="password")
                with st.expander("Advanced"):
                    include_system = st.checkbox("Include SYS* schemas", value=False)
                    max_workers = st.slider("Parallel connections", 1, 32, 8)

            with st.container(border=True, key="oe_fleet_panel"):
                fleet_header, fleet_actions = st.columns([3, 2])
                with fleet_header:
                    panel_title("Database Fleet")
                    st.caption(f"{len(st.session_state.db_list_df)} database(s) configured")
                with fleet_actions:
                    save_col, reset_col = st.columns(2)
                    with save_col:
                        if st.button("Save", key="oe_save_fleet", use_container_width=True):
                            to_save = connections_from_rows(
                                st.session_state.db_list_df.itertuples(index=False, name=None)
                            )
                            try:
                                save_connections(CONNECTIONS_FILE, to_save)
                                st.toast(f"Saved {len(to_save)} database(s).")
                            except OSError as exc:
                                st.error(f"Could not save: {exc}")
                    with reset_col:
                        if st.button("Reset", key="oe_reset_fleet", use_container_width=True):
                            st.session_state.db_list_df = _empty_db_frame()
                            st.session_state.pop("db_editor", None)
                            st.rerun()

                with st.expander("Paste from Excel or JDBC URL"):
                    st.caption("Paste rows (Database, Host, Port) or one JDBC URL per line.")
                    paste_text = st.text_area(
                        "Paste area",
                        height=88,
                        placeholder="jdbc:db2://ss-db22d:50000/infoq",
                        key="excel_paste_area",
                        label_visibility="collapsed",
                    )
                    paste_mode = st.radio(
                        "After paste",
                        ["Append to list", "Replace list"],
                        horizontal=True,
                        key="paste_mode",
                    )
                    if st.button("Apply pasted rows", type="primary", key="oe_apply_paste"):
                        pasted = parse_pasted_table(paste_text)
                        if not pasted:
                            st.warning("No valid rows found.")
                        else:
                            st.session_state.db_list_df = _merge_paste_into_frame(
                                st.session_state.db_list_df,
                                pasted,
                                replace=(paste_mode == "Replace list"),
                            )
                            st.session_state.pop("db_editor", None)
                            st.session_state.pop("excel_paste_area", None)
                            st.toast(f"Applied {len(pasted)} row(s).")
                            st.rerun()

                with st.container(key="oe_fleet_table"):
                    edited_df = st.data_editor(
                        st.session_state.db_list_df,
                        num_rows="dynamic",
                        width="stretch",
                        hide_index=True,
                        height=500,
                        key="db_editor",
                        column_config={
                            "Database": st.column_config.TextColumn("Database", required=True),
                            "Host": st.column_config.TextColumn("Host", required=True),
                            "Port": st.column_config.NumberColumn(
                                "Port", default=50000, min_value=1, max_value=65535
                            ),
                        },
                    )
                st.session_state.db_list_df = edited_df

    with right_col:
        with st.container(key="oe_right_column"):
            with st.container(border=True, key="oe_search_panel"):
                panel_title("Search criteria")
                type_index = (
                    OBJECT_TYPES.index(st.session_state.oe_object_type)
                    if st.session_state.oe_object_type in OBJECT_TYPES
                    else 0
                )
                search_row1_type, search_row1_text, search_row1_btn = st.columns([2, 3, 2])
                with search_row1_type:
                    st.selectbox(
                        "Object type",
                        options=OBJECT_TYPES,
                        index=type_index,
                        key="oe_object_type",
                    )
                with search_row1_text:
                    filter_text = st.text_input(
                        "Text to match",
                        placeholder="e.g. sp_refresh",
                        help="Case-insensitive.",
                        key="oe_filter_text",
                    )
                with search_row1_btn:
                    st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
                    search_clicked = st.button(
                        "Search all databases",
                        type="primary",
                        use_container_width=True,
                        key="oe_search_btn",
                    )
                operator = st.radio(
                    "Match mode",
                    MATCH_ORDER,
                    horizontal=True,
                    key="oe_match",
                )

            with st.container(border=True, key="oe_results_panel"):
                panel_title("Results")

                if search_clicked:
                    errors: list[str] = []
                    if not username or not password:
                        errors.append("Username and password are required.")
                    if not connections:
                        errors.append("Add at least one database to the fleet.")
                    if errors:
                        for err in errors:
                            st.error(err)
                    else:
                        progress = st.progress(0.0, text="Connecting to databases…")

                        def _on_progress(done: int, total: int) -> None:
                            progress.progress(done / total, text=f"Queried {done}/{total} databases")

                        with st.spinner("Querying databases…"):
                            query_results = run_across_databases(
                                connections,
                                username,
                                password,
                                st.session_state.oe_object_type,
                                operator,
                                filter_text,
                                include_system=include_system,
                                max_workers=max_workers,
                                on_progress=_on_progress,
                            )
                        progress.empty()
                        st.session_state.results = query_results
                        st.session_state.last_meta = {
                            "object_type": st.session_state.oe_object_type,
                            "operator": operator,
                            "text": filter_text,
                        }

                results = st.session_state.results
                if results is None:
                    st.markdown(
                        '<div class="ms-oe-empty">Run a search to see catalog objects across your fleet.</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    with st.container(key="oe_results_summary"):
                        meta = st.session_state.last_meta
                        st.caption(
                            f"**{meta.get('object_type')}** · {meta.get('operator')} · "
                            f"“{meta.get('text') or 'any'}”"
                        )

                        ok_results = [r for r in results if r.ok]
                        failed = [r for r in results if r.status in ("unreachable", "error")]
                        dbs_with_matches = [r for r in ok_results if r.match_count > 0]
                        total_matches = sum(r.match_count for r in ok_results)

                        m1, m2, m3, m4, m5 = st.columns(5)
                        m1.metric("Scanned", len(results))
                        m2.metric("Reachable", len(ok_results))
                        m3.metric("Failed", len(failed))
                        m4.metric("Databases with matches", len(dbs_with_matches))
                        m5.metric("Objects", total_matches)

                        df = results_to_frame(results)
                        toolbar_left, toolbar_right = st.columns([2, 1])
                        with toolbar_left:
                            show_only_matches = st.checkbox(
                                "Matches only", value=False, key="oe_matches_only"
                            )
                        with toolbar_right:
                            st.download_button(
                                "Download CSV",
                                data=df.to_csv(index=False).encode("utf-8"),
                                file_name="db2_object_search_results.csv",
                                mime="text/csv",
                                use_container_width=True,
                            )

                        if failed:
                            with st.expander(f"Errors ({len(failed)})"):
                                for r in failed:
                                    st.write(
                                        f"**{r.connection.dbname}** — `{r.status}`: {r.error}"
                                    )

                    view_df = df[df["Object Name"].astype(str) != ""] if show_only_matches else df
                    with st.container(key="oe_results_table"):
                        st.dataframe(view_df, width="stretch", hide_index=True, height=500)
