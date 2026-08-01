"""DB2 Migration Studio — home page (stitch_exports/03-home index.html)."""

from __future__ import annotations

from db2_explorer.ui.fleet_panel import handle_object_explorer_home_clear
from db2_explorer.api.register import ensure_oe_search_api
from db2_explorer.ui.stitch_page import render_home_page
from db2_explorer.ui.stitch_shell import handle_home_navigation
from db2_explorer.ui.theme import apply_page

apply_page(title="DB2 Migration Studio", layout="wide", home=True)

# Must run before render — card links use ?go=… which st.switch_page resolves to /Object_Explorer etc.
handle_home_navigation()

ensure_oe_search_api()  # best-effort; search falls back to page reload if unavailable
handle_object_explorer_home_clear()

render_home_page()
