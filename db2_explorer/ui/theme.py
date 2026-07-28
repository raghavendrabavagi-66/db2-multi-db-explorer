"""Global Streamlit theme — DB2 Migration Studio design system (UI UX Pro Max)."""

from __future__ import annotations

import streamlit as st

# Design tokens (design-system/db2-migration-studio/MASTER.md)
COLORS = {
    "primary": "#1E40AF",
    "primary_dark": "#1E3A8A",
    "secondary": "#3B82F6",
    "accent": "#D97706",
    "background": "#F8FAFC",
    "surface": "#FFFFFF",
    "muted": "#E9EEF6",
    "border": "#DBEAFE",
    "text": "#1E3A8A",
    "text_muted": "#475569",
    "success": "#059669",
    "destructive": "#DC2626",
}

FONT_IMPORT = (
    "https://fonts.googleapis.com/css2?"
    "family=Fira+Code:wght@400;500;600&"
    "family=Fira+Sans:wght@300;400;500;600;700&display=swap"
)

GLOBAL_CSS = f"""
@import url('{FONT_IMPORT}');

:root {{
    --ms-primary: {COLORS['primary']};
    --ms-primary-dark: {COLORS['primary_dark']};
    --ms-accent: {COLORS['accent']};
    --ms-bg: {COLORS['background']};
    --ms-surface: {COLORS['surface']};
    --ms-border: {COLORS['border']};
    --ms-text: {COLORS['text']};
    --ms-text-muted: {COLORS['text_muted']};
}}

html, body, [class*="css"] {{
    font-family: 'Fira Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}}

code, pre, .stCodeBlock {{
    font-family: 'Fira Code', ui-monospace, monospace !important;
}}

/* App chrome */
.block-container {{
    padding-top: 1.25rem;
    padding-bottom: 2rem;
    max-width: 1280px;
}}

/* Sidebar */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    border-right: 1px solid rgba(255,255,255,0.06);
}}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span {{
    color: #e2e8f0 !important;
}}
section[data-testid="stSidebar"] .stTextInput input {{
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.12);
    color: #f8fafc;
}}

/* Primary buttons */
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {{
    background: linear-gradient(135deg, {COLORS['primary']} 0%, {COLORS['secondary']} 100%);
    border: none;
    font-weight: 600;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}}
.stButton > button[kind="primary"]:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(30, 64, 175, 0.35);
}}

/* Metrics */
div[data-testid="stMetric"] {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    padding: 0.75rem 1rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}}
div[data-testid="stMetric"] label {{
    color: {COLORS['text_muted']} !important;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    color: {COLORS['primary_dark']} !important;
    font-weight: 700;
}}

/* Expanders & containers */
div[data-testid="stExpander"] {{
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    background: {COLORS['surface']};
    overflow: hidden;
}}
div[data-testid="stExpander"] details {{
    border: none;
}}

[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 14px !important;
    border-color: {COLORS['border']} !important;
    background: {COLORS['surface']};
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}}

/* Dataframes */
.stDataFrame {{
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    overflow: hidden;
}}

/* Hide Streamlit chrome on home */
.ms-hide-nav .stApp > header {{
    visibility: hidden;
}}
.ms-hide-nav #MainMenu {{
    visibility: hidden;
}}
.ms-hide-nav footer {{
    visibility: hidden;
}}

@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }}
}}
"""

SCHEMA_COMPARE_CSS = """
/* Schema compare: split pane layout */
[data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"] > div[key="sch_objects_pane"]) {
    min-height: 520px;
}
[data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stVerticalBlock"] > div[key="sch_ddl_pane"]) {
    min-height: 420px;
}
"""


def inject_global_styles(*, schema_compare: bool = False) -> None:
    """Inject design-system CSS once per run."""
    css = GLOBAL_CSS
    if schema_compare:
        css += SCHEMA_COMPARE_CSS
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def apply_page(
    *,
    title: str,
    icon: str = "",
    layout: str = "wide",
    sidebar_expanded: bool = True,
    schema_compare: bool = False,
) -> None:
    """Standard page bootstrap: config + global styles."""
    page_title = f"{icon} {title}".strip() if icon else title
    st.set_page_config(
        page_title=page_title,
        page_icon="🗄️",
        layout=layout,
        initial_sidebar_state="expanded" if sidebar_expanded else "collapsed",
    )
    inject_global_styles(schema_compare=schema_compare)
