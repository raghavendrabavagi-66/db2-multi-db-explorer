"""DB2 Multi-DB Object Explorer - Streamlit UI.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from connections_loader import (
    CONNECTIONS_FILE,
    Connection,
    connections_from_rows,
    load_paths,
    parse_pasted_table,
    save_connections,
)
from db2_client import DBResult, run_across_databases
from queries import MATCH_ORDER, OBJECT_TYPES

st.set_page_config(page_title="DB2 Multi-DB Object Explorer", layout="wide")

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
    """Seed the editable table from the persisted connections file, if present."""
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


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Sidebar: credentials + options
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Connection")
    username = st.text_input("Username", key="username")
    password = st.text_input("Password", type="password", key="password")

    st.divider()
    include_system = st.checkbox("Include system objects (SYS* schemas)", value=False)
    max_workers = st.slider("Parallel connections", 1, 32, 8)


connections = connections_from_rows(
    st.session_state.db_list_df.itertuples(index=False, name=None)
)


# ---------------------------------------------------------------------------
# Main: object-type buttons (first-level filter)
# ---------------------------------------------------------------------------
st.title("DB2 Multi-DB Object Explorer")
st.caption(
    "Trace database objects across many DB2 LUW databases at once. "
    "Pick an object type, set a name filter, and run."
)

# ---------------------------------------------------------------------------
# Databases: in-app editable connection list
# ---------------------------------------------------------------------------
st.subheader("Databases")
dbcol1, dbcol2 = st.columns([3, 1])
with dbcol1:
    st.caption(f"{len(connections)} database(s) configured.")
with dbcol2:
    edit_label = "Close editor" if st.session_state.show_db_editor else "Edit DB list"
    if st.button(edit_label, use_container_width=True):
        st.session_state.show_db_editor = not st.session_state.show_db_editor
        st.rerun()

if st.session_state.show_db_editor:
    with st.expander("Paste from Excel or DBeaver JDBC URL", expanded=True):
        st.caption(
            "Paste **Excel rows** (Database, Host, Port) or **DBeaver JDBC URLs** (one per line), "
            "e.g. `jdbc:db2://ss-db22d:50000/infoq` → Database **infoq**, Host **ss-db22d**, Port **50000**. "
            "Multi-row paste does not work inside the table cells."
        )
        paste_text = st.text_area(
            "Paste area",
            height=120,
            placeholder=(
                "jdbc:db2://ss-db22d:50000/infoq\n"
                "jdbc:db2://ss-db22d:50000/testdb"
            ),
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
                st.warning(
                    "No valid rows found. Paste Excel rows (Database, Host, Port) or a "
                    "DBeaver URL like jdbc:db2://ss-db22d:50000/infoq"
                )
            else:
                st.session_state.db_list_df = _merge_paste_into_frame(
                    st.session_state.db_list_df,
                    pasted,
                    replace=(paste_mode == "Replace list"),
                )
                st.session_state.pop("db_editor", None)
                st.session_state.pop("excel_paste_area", None)
                verb = "Replaced with" if paste_mode == "Replace list" else "Added"
                st.toast(f"{verb} {len(pasted)} row(s) from paste.")
                st.rerun()

    st.caption(
        "Edit individual cells below, or use **Paste from Excel** above for multiple rows. "
        "Port defaults to 50000."
    )
    edited_df = st.data_editor(
        st.session_state.db_list_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="db_editor",
        column_config={
            "Database": st.column_config.TextColumn(
                "Database", required=True, help="DB2 database name"
            ),
            "Host": st.column_config.TextColumn(
                "Host", required=True, help="Hostname or IP"
            ),
            "Port": st.column_config.NumberColumn(
                "Port",
                help="TCP port (default 50000)",
                default=50000,
                min_value=1,
                max_value=65535,
                step=1,
                format="%d",
            ),
        },
    )
    st.session_state.db_list_df = edited_df

    save_col, reset_col, _ = st.columns([1, 1, 3])
    with save_col:
        if st.button("Save to file", use_container_width=True):
            to_save = connections_from_rows(
                st.session_state.db_list_df.itertuples(index=False, name=None)
            )
            try:
                save_connections(CONNECTIONS_FILE, to_save)
                st.toast(f"Saved {len(to_save)} database(s) to {CONNECTIONS_FILE}")
            except OSError as exc:
                st.error(f"Could not save: {exc}")
    with reset_col:
        if st.button("Reset", use_container_width=True):
            st.session_state.db_list_df = _empty_db_frame()
            # Clear the editor's tracked edits so they aren't re-applied.
            st.session_state.pop("db_editor", None)
            st.rerun()

st.divider()

st.subheader("1. Object type")
cols = st.columns(5)
for i, obj_type in enumerate(OBJECT_TYPES):
    col = cols[i % 5]
    is_selected = st.session_state.selected_type == obj_type
    if col.button(
        obj_type,
        key=f"objbtn_{obj_type}",
        use_container_width=True,
        type="primary" if is_selected else "secondary",
    ):
        st.session_state.selected_type = obj_type
        st.rerun()

st.info(f"Selected object type: **{st.session_state.selected_type}**")


# ---------------------------------------------------------------------------
# Second-level filter: match operator + text
# ---------------------------------------------------------------------------
st.subheader("2. Name filter")
fcol1, fcol2 = st.columns([1, 2])
with fcol1:
    operator = st.radio("Match", MATCH_ORDER, horizontal=False)
with fcol2:
    filter_text = st.text_input(
        "Text to match",
        placeholder="e.g. sp_refresh",
        help="Matching is case-insensitive.",
    )
    st.caption(f"{len(connections)} database(s) configured.")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
st.subheader("3. Run")
run_clicked = st.button("Search across all databases", type="primary")

if run_clicked:
    errors = []
    if not username or not password:
        errors.append("Username and password are required.")
    if not connections:
        errors.append("No databases configured. Click 'Edit DB list' to add some.")
    if not filter_text and operator != "anywhere":
        # 'anywhere' with empty text would match everything; warn but allow.
        pass

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


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
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
    st.divider()
    st.subheader("Results")
    st.caption(
        f"Object type: **{meta.get('object_type')}** | "
        f"Match: **{meta.get('operator')}** | Text: **{meta.get('text') or '(any)'}**"
    )

    total_dbs = len(results)
    reachable = [r for r in results if r.status in ("ok", "no matches")]
    ok_results = [r for r in results if r.ok]
    failed = [r for r in results if r.status in ("unreachable", "error")]
    dbs_with_matches = [r for r in ok_results if r.match_count > 0]
    total_matches = sum(r.match_count for r in ok_results)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Databases scanned", total_dbs)
    m2.metric("Reachable", len(ok_results))
    m3.metric("Failed", len(failed))
    m4.metric("DBs with matches", len(dbs_with_matches))
    m5.metric("Total objects found", total_matches)

    st.success(
        f"{len(dbs_with_matches)} of {len(ok_results)} reachable database(s) "
        f"have matching **{meta.get('object_type')}** objects."
    )

    df = results_to_frame(results)

    show_only_matches = st.checkbox("Show only rows with matches", value=False)
    view_df = df
    if show_only_matches:
        view_df = df[df["Object Name"].astype(str) != ""]

    st.dataframe(view_df, use_container_width=True, hide_index=True)

    st.download_button(
        "Download results as CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="db2_object_search_results.csv",
        mime="text/csv",
    )

    if failed:
        with st.expander(f"Connection / query errors ({len(failed)})"):
            for r in failed:
                st.write(
                    f"**{r.connection.dbname}** @ {r.connection.host}:"
                    f"{r.connection.port} - `{r.status}`: {r.error}"
                )
