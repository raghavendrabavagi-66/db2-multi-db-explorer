"""DB2 Migration Studio — home and navigation hub.

Run:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from db2_explorer.ui.components import (
    ICON_COMPARE,
    ICON_SCHEMA,
    ICON_SEARCH,
    feature_card,
    page_header,
    sidebar_brand,
)
from db2_explorer.ui.theme import COLORS, inject_global_styles

st.set_page_config(
    page_title="DB2 Migration Studio",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_global_styles()

with st.sidebar:
    sidebar_brand()
    st.markdown("---")
    st.markdown("**Workspace**")
    st.page_link("app.py", label="Home", icon="🏠")
    st.page_link("pages/1_Object_Explorer.py", label="Object Explorer", icon="🔍")
    st.page_link("pages/2_Row_Compare.py", label="Row Compare", icon="📊")
    st.page_link("pages/3_Schema_Compare.py", label="Schema Compare", icon="🔄")
    st.markdown("---")
    st.caption("Design system: Data-Dense Dashboard · Fira Sans")

page_header(
    "DB2 Migration Studio",
    subtitle=(
        "Explore DB2 catalogs across fleets, validate row counts against Azure SQL, "
        "and reconcile GitLab deployment DDL with live target databases — in one workspace."
    ),
    badge="Enterprise",
)

# Hero metrics strip
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Services", "3", "Multipage")
with c2:
    st.metric("Sources", "DB2 + GitLab", "")
with c3:
    st.metric("Targets", "Azure / SQL Server", "")
with c4:
    st.metric("Sync", "Constraints + Indexes", "")

st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

st.markdown(
    f"""
    <div style="background: linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['primary_dark']} 100%);
                color: white; border-radius: 18px; padding: 1.75rem 2rem; margin-bottom: 1.5rem;
                box-shadow: 0 8px 24px rgba(30, 64, 175, 0.25);">
        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em;
                    opacity: 0.85; margin-bottom: 0.5rem;">Migration intelligence</div>
        <div style="font-size: 1.35rem; font-weight: 650; line-height: 1.35; max-width: 640px;">
            From catalog discovery to schema drift remediation — purpose-built for DB2 LUW
            to Azure SQL migration programs.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Choose a workflow")
col1, col2, col3 = st.columns(3)

with col1:
    feature_card(
        "Object Explorer",
        "Search procedures, tables, views, and more across many DB2 databases in parallel. "
        "Paste JDBC URLs or manage connection lists inline.",
        icon_svg=ICON_SEARCH,
        accent=COLORS["primary"],
    )
    if st.button("Open Object Explorer", key="nav_obj", type="primary", width="stretch"):
        st.switch_page("pages/1_Object_Explorer.py")

with col2:
    feature_card(
        "Row Compare",
        "Map DB2 schemas to Azure SQL and compare table row counts. "
        "Bulk LISTAGG with per-table fallback for large fleets.",
        icon_svg=ICON_COMPARE,
        accent=COLORS["secondary"],
    )
    if st.button("Open Row Compare", key="nav_row", width="stretch"):
        st.switch_page("pages/2_Row_Compare.py")

with col3:
    feature_card(
        "Schema Compare",
        "Load GitLab deployment DDL, diff against live target definitions, "
        "and apply constraint or index drift with transactional sync.",
        icon_svg=ICON_SCHEMA,
        accent=COLORS["accent"],
    )
    if st.button("Open Schema Compare", key="nav_schema", width="stretch"):
        st.switch_page("pages/3_Schema_Compare.py")

st.markdown("---")
with st.expander("Quick start"):
    st.markdown(
        """
        1. **Object Explorer** — Add databases under *Edit DB list*, pick an object type, filter, and search.
        2. **Row Compare** — Connect DB2 source + Azure target, map schemas, run comparison.
        3. **Schema Compare** — Enter GitLab PAT, load deployment, connect target, *Compare all*.

        Azure AD sign-in opens once per session. On-prem SQL Server targets use Windows integrated auth on Windows hosts.
        """
    )
