"""Object Explorer — search DB2 catalog objects across many databases."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from db2_explorer.clients.db2 import DBResult, run_across_databases
from db2_explorer.data.connections import (
    CONNECTIONS_FILE,
    Connection,
    connections_from_rows,
    load_paths,
    parse_pasted_table,
    save_connections,
)
from db2_explorer.data.queries import MATCH_ORDER, OBJECT_TYPES
from db2_explorer.ui.components import section_card, service_top_bar
from db2_explorer.ui.theme import apply_page

apply_page(title="Object Explorer", layout="wide")

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


if "selected_type" not in st.session_state:
    st.session_state.selected_type = OBJECT_TYPES[0]
if "results" not in st.session_state:
    st.session_state.results = None
if "last_meta" not in st.session_state:
    st.session_state.last_meta = {}
if "db_list_df" not in st.session_state:
    st.session_state.db_list_df = _load_saved_db_frame()
if "show_db_editor" not in st.session_state:
    st.session_state.show_db_editor = False

service_top_bar(
    "Object Explorer",
    tagline="Trace database objects across many DB2 LUW databases at once.",
    home_key="oe_home",
)

connections = connections_from_rows(
    st.session_state.db_list_df.itertuples(index=False, name=None)
)

with st.expander("Connection settings", expanded=True):
    cred1, cred2, cred3, cred4 = st.columns([2, 2, 2, 2])
    with cred1:
        username = st.text_input("Username", key="username")
    with cred2:
        password = st.text_input("Password", type="password", key="password")
    with cred3:
        include_system = st.checkbox("Include system objects (SYS* schemas)", value=False)
    with cred4:
        max_workers = st.slider("Parallel connections", 1, 32, 8)

section_card("Database fleet", help_text=f"{len(connections)} database(s) configured")
dbcol1, dbcol2 = st.columns([3, 1])
with dbcol1:
    st.caption("Manage the list of DB2 instances to query in parallel.")
with dbcol2:
    edit_label = "Close editor" if st.session_state.show_db_editor else "Edit DB list"
    if st.button(edit_label, width="stretch"):
        st.session_state.show_db_editor = not st.session_state.show_db_editor
        st.rerun()

if st.session_state.show_db_editor:
    with st.expander("Paste from Excel or DBeaver JDBC URL", expanded=True):
        st.caption(
            "Paste **Excel rows** (Database, Host, Port) or **DBeaver JDBC URLs** (one per line)."
        )
        paste_text = st.text_area(
            "Paste area",
            height=120,
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
        if st.button("Apply pasted rows", type="primary"):
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

    edited_df = st.data_editor(
        st.session_state.db_list_df,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key="db_editor",
        column_config={
            "Database": st.column_config.TextColumn("Database", required=True),
            "Host": st.column_config.TextColumn("Host", required=True),
            "Port": st.column_config.NumberColumn("Port", default=50000, min_value=1, max_value=65535),
        },
    )
    st.session_state.db_list_df = edited_df

    save_col, reset_col, _ = st.columns([1, 1, 3])
    with save_col:
        if st.button("Save to file", width="stretch"):
            to_save = connections_from_rows(
                st.session_state.db_list_df.itertuples(index=False, name=None)
            )
            try:
                save_connections(CONNECTIONS_FILE, to_save)
                st.toast(f"Saved {len(to_save)} database(s).")
            except OSError as exc:
                st.error(f"Could not save: {exc}")
    with reset_col:
        if st.button("Reset", width="stretch"):
            st.session_state.db_list_df = _empty_db_frame()
            st.session_state.pop("db_editor", None)
            st.rerun()

section_card("Search criteria")
cols = st.columns(5)
for i, obj_type in enumerate(OBJECT_TYPES):
    col = cols[i % 5]
    is_selected = st.session_state.selected_type == obj_type
    if col.button(
        obj_type,
        key=f"objbtn_{obj_type}",
        width="stretch",
        type="primary" if is_selected else "secondary",
    ):
        st.session_state.selected_type = obj_type
        st.rerun()

fcol1, fcol2 = st.columns([1, 2])
with fcol1:
    operator = st.radio("Match", MATCH_ORDER, horizontal=False)
with fcol2:
    filter_text = st.text_input(
        "Text to match",
        placeholder="e.g. sp_refresh",
        help="Case-insensitive.",
    )

if st.button("Search across all databases", type="primary"):
    errors = []
    if not username or not password:
        errors.append("Username and password are required.")
    if not connections:
        errors.append("No databases configured. Click 'Edit DB list' to add some.")
    if errors:
        for e in errors:
            st.error(e)
    else:
        progress = st.progress(0.0, text="Connecting to databases...")

        def _on_progress(done: int, total: int) -> None:
            progress.progress(done / total, text=f"Queried {done}/{total} databases")

        with st.spinner("Querying databases..."):
            results = run_across_databases(
                connections,
                username,
                password,
                st.session_state.selected_type,
                operator,
                filter_text,
                include_system=include_system,
                max_workers=max_workers,
                on_progress=_on_progress,
            )
        progress.empty()
        st.session_state.results = results
        st.session_state.last_meta = {
            "object_type": st.session_state.selected_type,
            "operator": operator,
            "text": filter_text,
        }


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


results = st.session_state.results
if results is not None:
    meta = st.session_state.last_meta
    section_card("Results")
    st.caption(
        f"Object type: **{meta.get('object_type')}** | "
        f"Match: **{meta.get('operator')}** | Text: **{meta.get('text') or '(any)'}**"
    )

    ok_results = [r for r in results if r.ok]
    failed = [r for r in results if r.status in ("unreachable", "error")]
    dbs_with_matches = [r for r in ok_results if r.match_count > 0]
    total_matches = sum(r.match_count for r in ok_results)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Databases scanned", len(results))
    m2.metric("Reachable", len(ok_results))
    m3.metric("Failed", len(failed))
    m4.metric("DBs with matches", len(dbs_with_matches))
    m5.metric("Total objects", total_matches)

    df = results_to_frame(results)
    show_only_matches = st.checkbox("Show only rows with matches", value=False)
    view_df = df[df["Object Name"].astype(str) != ""] if show_only_matches else df

    st.dataframe(view_df, width="stretch", hide_index=True)
    st.download_button(
        "Download CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="db2_object_search_results.csv",
        mime="text/csv",
    )

    if failed:
        with st.expander(f"Errors ({len(failed)})"):
            for r in failed:
                st.write(f"**{r.connection.dbname}** — `{r.status}`: {r.error}")
