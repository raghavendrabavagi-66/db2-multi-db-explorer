"""Database Fleet panel — editable multi-database connection list for Object Explorer."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from db2_explorer.data.connections import (
    CONNECTIONS_FILE,
    connections_from_rows,
    load_paths,
    parse_pasted_table,
    save_connections,
)
from db2_explorer.ui.stitch_shell import fleet_panel_header_html, render_html

# ── Column schema ──────────────────────────────────────────────────────────────

FLEET_COLUMNS = ["Database", "Host", "Port"]

SESSION_DF_KEY = "db_list_df"
EDITOR_WIDGET_KEY = "db_editor"
OE_CLEAR_QUERY_PARAM = "oe_clear"

OE_SESSION_KEYS = (
    SESSION_DF_KEY,
    EDITOR_WIDGET_KEY,
    "results",
    "last_meta",
    "username",
    "password",
    "oe_include_system",
    "oe_max_workers",
    "oe_object_type",
    "oe_match",
    "oe_filter_text",
    "oe_matches_only",
    "_oe_search_error",
)

_ROW_PX = 36
_HEADER_PX = 52
_EDITOR_MIN_PX = 220
_EDITOR_MAX_PX = 960


# ── Data helpers ───────────────────────────────────────────────────────────────


def empty_fleet_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=FLEET_COLUMNS)


def fleet_frame_from_rows(rows: list[tuple[str, str, int]]) -> pd.DataFrame:
    if not rows:
        return empty_fleet_frame()
    return pd.DataFrame(rows, columns=FLEET_COLUMNS)


def load_saved_fleet_frame() -> pd.DataFrame:
    if not os.path.isfile(CONNECTIONS_FILE):
        return empty_fleet_frame()
    try:
        conns = load_paths([CONNECTIONS_FILE])
    except OSError:
        return empty_fleet_frame()
    if not conns:
        return empty_fleet_frame()
    return pd.DataFrame(
        [[c.dbname, c.host, c.port] for c in conns],
        columns=FLEET_COLUMNS,
    )


def merge_paste(
    existing: pd.DataFrame,
    pasted: list[tuple[str, str, int]],
    *,
    replace: bool,
) -> pd.DataFrame:
    incoming = fleet_frame_from_rows(pasted)
    combined = incoming if replace else pd.concat([existing, incoming], ignore_index=True)
    conns = connections_from_rows(combined.itertuples(index=False, name=None))
    return fleet_frame_from_rows([(c.dbname, c.host, c.port) for c in conns])


def editor_height(row_count: int) -> int:
    """First-paint editor height — tall enough for all rows; JS fills panel remainder."""
    display_rows = max(row_count + 1, 4)  # +1 for dynamic "add row" slot
    content_px = display_rows * _ROW_PX + _HEADER_PX
    return max(_EDITOR_MIN_PX, min(_EDITOR_MAX_PX, content_px))


def _column_config() -> dict:
    return {
        "Database": st.column_config.TextColumn("Database", required=True, width="medium"),
        "Host": st.column_config.TextColumn("Host", required=True, width="medium"),
        "Port": st.column_config.NumberColumn(
            "Port",
            default=50000,
            min_value=1,
            max_value=65535,
            width="small",
        ),
    }


# ── Panel sections ─────────────────────────────────────────────────────────────


def _current_fleet_df(fallback: pd.DataFrame) -> pd.DataFrame:
    widget_df = st.session_state.get(EDITOR_WIDGET_KEY)
    if isinstance(widget_df, pd.DataFrame):
        return widget_df
    return fallback


def _render_header(df: pd.DataFrame) -> None:
    title_col, reset_col, save_col = st.columns([4, 1, 1])
    with title_col:
        render_html(fleet_panel_header_html(db_count=len(df)))
    with reset_col:
        st.markdown("<div style='padding-top:0.75rem'>", unsafe_allow_html=True)
        if st.button("Reset", key="oe_reset_fleet", use_container_width=True):
            st.session_state[SESSION_DF_KEY] = empty_fleet_frame()
            st.session_state.pop(EDITOR_WIDGET_KEY, None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with save_col:
        st.markdown("<div style='padding-top:0.75rem'>", unsafe_allow_html=True)
        if st.button("Save Fleet", key="oe_save_fleet", type="primary", use_container_width=True):
            to_save = connections_from_rows(
                _current_fleet_df(df).itertuples(index=False, name=None)
            )
            try:
                save_connections(CONNECTIONS_FILE, to_save)
                st.toast(f"Saved {len(to_save)} database(s).")
            except OSError as exc:
                st.error(f"Could not save: {exc}")
        st.markdown("</div>", unsafe_allow_html=True)


def _render_paste_expander() -> None:
    with st.expander("Paste from Excel/JDBC string"):
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
                return
            st.session_state[SESSION_DF_KEY] = merge_paste(
                st.session_state[SESSION_DF_KEY],
                pasted,
                replace=(paste_mode == "Replace list"),
            )
            st.session_state.pop(EDITOR_WIDGET_KEY, None)
            st.session_state.pop("excel_paste_area", None)
            st.toast(f"Applied {len(pasted)} row(s).")
            st.rerun()


def _render_editor(df: pd.DataFrame) -> pd.DataFrame:
    """Editable grid — direct child of the fleet panel (keyed for layout CSS/JS)."""
    return st.data_editor(
        df,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        height=editor_height(len(df)),
        key=EDITOR_WIDGET_KEY,
        column_config=_column_config(),
    )


# ── Public API ─────────────────────────────────────────────────────────────────


def clear_object_explorer_session() -> None:
    """Drop all Object Explorer session keys, including credentials."""
    for key in OE_SESSION_KEYS:
        st.session_state.pop(key, None)


def handle_object_explorer_home_clear() -> None:
    """Clear OE session when navigating home via ?oe_clear=1."""
    if st.query_params.get(OE_CLEAR_QUERY_PARAM) != "1":
        return
    clear_object_explorer_session()
    st.query_params.clear()


def ensure_fleet_session_state() -> None:
    if SESSION_DF_KEY not in st.session_state:
        st.session_state[SESSION_DF_KEY] = load_saved_fleet_frame()


def render_database_fleet() -> pd.DataFrame:
    """Render the Database Fleet bordered panel and return the edited dataframe."""
    ensure_fleet_session_state()
    df = st.session_state[SESSION_DF_KEY]

    with st.container(border=True, key="oe_fleet_panel"):
        _render_header(df)
        _render_paste_expander()
        edited_df = _render_editor(df)

    st.session_state[SESSION_DF_KEY] = edited_df
    return edited_df
