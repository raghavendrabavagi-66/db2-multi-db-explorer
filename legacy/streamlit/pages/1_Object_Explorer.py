"""Object Explorer — exact stitch 02-object-explorer HTML + live backend."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from db2_explorer.clients.db2 import run_across_databases
from db2_explorer.data.connections import connections_from_rows, parse_pasted_table
from db2_explorer.data.queries import MATCH_ORDER, OBJECT_TYPES
from db2_explorer.ui.fleet_panel import (
    SESSION_DF_KEY,
    empty_fleet_frame,
    fleet_frame_from_rows,
    merge_paste,
)
from db2_explorer.ui.stitch_page import ObjectExplorerView, render_object_explorer_page
from db2_explorer.ui.theme import apply_page

apply_page(title="Object Explorer", layout="wide", object_explorer=True)


def _ensure_session() -> None:
    if SESSION_DF_KEY not in st.session_state:
        st.session_state[SESSION_DF_KEY] = empty_fleet_frame()
    if "results" not in st.session_state:
        st.session_state.results = None
    if "last_meta" not in st.session_state:
        st.session_state.last_meta = {}
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "password" not in st.session_state:
        st.session_state.password = ""
    if "oe_include_system" not in st.session_state:
        st.session_state.oe_include_system = False
    if "oe_max_workers" not in st.session_state:
        st.session_state.oe_max_workers = 8
    if "oe_object_type" not in st.session_state:
        st.session_state.oe_object_type = OBJECT_TYPES[0]
    if "oe_match" not in st.session_state:
        st.session_state.oe_match = MATCH_ORDER[0]
    if "oe_filter_text" not in st.session_state:
        st.session_state.oe_filter_text = ""
    if "oe_matches_only" not in st.session_state:
        st.session_state.oe_matches_only = False


def _apply_connection_params() -> None:
    if "username" in st.query_params:
        st.session_state.username = st.query_params.get("username", "")
    if "password" in st.query_params:
        st.session_state.password = st.query_params.get("password", "")
    if "include_system" in st.query_params:
        st.session_state.oe_include_system = st.query_params.get("include_system", "0") == "1"
    if "max_workers" in st.query_params:
        try:
            st.session_state.oe_max_workers = int(st.query_params.get("max_workers", "8"))
        except ValueError:
            st.session_state.oe_max_workers = 8


def _apply_fleet_json() -> None:
    raw = st.query_params.get("fleet_json", "")
    if not raw:
        return
    try:
        rows = json.loads(raw)
        parsed: list[tuple[str, str, int]] = []
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) < 2:
                continue
            db, host = str(row[0]).strip(), str(row[1]).strip()
            if not db or not host:
                continue
            try:
                port = int(row[2]) if len(row) > 2 else 50000
            except (TypeError, ValueError):
                port = 50000
            parsed.append((db, host, port))
        st.session_state[SESSION_DF_KEY] = fleet_frame_from_rows(parsed)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass


def _handle_query_actions() -> None:
    action = st.query_params.get("oe_action", "")
    if not action:
        return

    if action == "reset":
        st.session_state[SESSION_DF_KEY] = empty_fleet_frame()
        st.session_state.results = None
        st.session_state.last_meta = {}
        st.session_state.oe_matches_only = False
    elif action == "hydrate":
        _apply_fleet_json()
    elif action == "save":
        _apply_connection_params()
        _apply_fleet_json()
        df = st.session_state.get(SESSION_DF_KEY, empty_fleet_frame())
        count = len(connections_from_rows(df.itertuples(index=False, name=None)))
        st.toast(f"Saved {count} database(s) to browser storage.")
    elif action == "paste":
        _apply_fleet_json()
        paste_text = st.query_params.get("paste_text", "")
        pasted = parse_pasted_table(paste_text)
        if pasted:
            mode = st.query_params.get("paste_mode", "append")
            st.session_state[SESSION_DF_KEY] = merge_paste(
                st.session_state.get(SESSION_DF_KEY, empty_fleet_frame()),
                pasted,
                replace=(mode == "replace"),
            )
            st.toast(f"Applied {len(pasted)} row(s).")
        else:
            st.session_state._oe_search_error = "No valid rows found in pasted text."
    elif action == "search":
        _apply_connection_params()
        _apply_fleet_json()
        st.session_state.oe_filter_text = st.query_params.get("filter_text", "")
        obj = st.query_params.get("object_type", OBJECT_TYPES[0])
        if obj in OBJECT_TYPES:
            st.session_state.oe_object_type = obj
        op = st.query_params.get("operator", MATCH_ORDER[0])
        if op in MATCH_ORDER:
            st.session_state.oe_match = op
        _run_search()
    elif action == "toggle_matches":
        st.session_state.oe_matches_only = st.query_params.get("matches_only", "0") == "1"

    st.query_params.clear()


def _run_search() -> None:
    df = st.session_state.get(SESSION_DF_KEY, empty_fleet_frame())
    connections = connections_from_rows(df.itertuples(index=False, name=None))
    username = st.session_state.username
    password = st.session_state.password
    if not username or not password:
        st.session_state._oe_search_error = "Username and password are required."
        return
    if not connections:
        st.session_state._oe_search_error = "Add at least one database to the fleet."
        return
    st.session_state._oe_search_error = ""
    st.session_state.results = run_across_databases(
        connections,
        username,
        password,
        st.session_state.oe_object_type,
        st.session_state.oe_match,
        st.session_state.oe_filter_text,
        include_system=st.session_state.oe_include_system,
        max_workers=st.session_state.oe_max_workers,
    )
    st.session_state.last_meta = {
        "object_type": st.session_state.oe_object_type,
        "operator": st.session_state.oe_match,
        "text": st.session_state.oe_filter_text,
        "scan_time_ms": sum(r.elapsed_ms for r in st.session_state.results),
    }


_ensure_session()
_handle_query_actions()

if err := st.session_state.pop("_oe_search_error", ""):
    st.error(err)

df: pd.DataFrame = st.session_state.get(SESSION_DF_KEY, empty_fleet_frame())
fleet_rows = [tuple(row) for row in df.itertuples(index=False, name=None)]

view = ObjectExplorerView(
    username=st.session_state.username,
    password=st.session_state.password,
    include_system=st.session_state.oe_include_system,
    max_workers=st.session_state.oe_max_workers,
    object_type=st.session_state.oe_object_type,
    operator=st.session_state.oe_match,
    filter_text=st.session_state.oe_filter_text,
    fleet_rows=fleet_rows,
    results=st.session_state.results,
    last_meta=st.session_state.last_meta,
    show_matches_only=st.session_state.oe_matches_only,
)

render_object_explorer_page(view)
