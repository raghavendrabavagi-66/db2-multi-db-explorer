"""DB2 Migration Studio — home launcher.

Run:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from db2_explorer.ui.components import (
    ICON_COMPARE,
    ICON_SCHEMA,
    ICON_SEARCH,
    home_footer,
    home_hero,
    home_service_card,
)
from db2_explorer.ui.theme import COLORS, apply_page

apply_page(title="DB2 Migration Studio", layout="wide", home=True)

home_hero(
    title="DB2 Migration Studio",
    subtitle="Choose a workflow to explore catalogs, validate row counts, or reconcile schema drift.",
)

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    home_service_card(
        "Object Explorer",
        "Search tables, procedures, and views across many DB2 databases.",
        icon_svg=ICON_SEARCH,
        accent=COLORS["primary"],
    )
    if st.button("Enter →", key="home_nav_obj", use_container_width=True):
        st.switch_page("pages/1_Object_Explorer.py")

with col2:
    home_service_card(
        "Row Compare",
        "Compare table row counts between DB2 source and Azure SQL target.",
        icon_svg=ICON_COMPARE,
        accent=COLORS["secondary"],
    )
    if st.button("Enter →", key="home_nav_row", use_container_width=True):
        st.switch_page("pages/2_Row_Compare.py")

with col3:
    home_service_card(
        "Schema Compare",
        "Diff GitLab deployment DDL against live target definitions.",
        icon_svg=ICON_SCHEMA,
        accent=COLORS["accent"],
    )
    if st.button("Enter →", key="home_nav_sch", use_container_width=True):
        st.switch_page("pages/3_Schema_Compare.py")

home_footer()
