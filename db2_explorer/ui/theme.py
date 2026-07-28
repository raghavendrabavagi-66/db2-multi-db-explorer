"""Global Streamlit theme — DB2 Migration Studio design system (UI UX Pro Max)."""

from __future__ import annotations

import streamlit as st

# Design tokens — clean white UI, blue primary (no navy/purple foreground)
COLORS = {
    "primary": "#2563EB",
    "primary_dark": "#1D4ED8",
    "secondary": "#3B82F6",
    "accent": "#D97706",
    "background": "#FFFFFF",
    "surface": "#FFFFFF",
    "muted": "#F1F5F9",
    "border": "#E2E8F0",
    "text": "#0F172A",
    "text_muted": "#64748B",
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

.stApp, section.main, .block-container {{
    background-color: {COLORS['background']} !important;
}}

code, pre, .stCodeBlock {{
    font-family: 'Fira Code', ui-monospace, monospace !important;
}}

/* App chrome — full width, no sidebar; top padding clears Streamlit stHeader (Deploy / menu) */
.block-container {{
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: none;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
}}

section[data-testid="stSidebar"],
section[data-testid="stSidebar"] ~ div[data-testid="collapsedControl"],
[data-testid="collapsedControl"] {{
    display: none !important;
}}

section.main > div {{
    max-width: none;
}}

/* Legacy sidebar styles (unused when sidebar hidden) */
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

/* Service top bar */
.ms-service-topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.5rem 0 1rem 0;
    margin-bottom: 0.25rem;
    border-bottom: 1px solid {COLORS['border']};
}}
.ms-service-topbar-brand {{
    font-size: 0.78rem;
    font-weight: 600;
    color: {COLORS['text_muted']};
    letter-spacing: 0.02em;
    white-space: nowrap;
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
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.28);
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
    color: {COLORS['text']} !important;
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

HOME_PAGE_CSS = f"""
/* Home — minimal launcher (UI UX Pro Max: Minimal Single Column, density 2) */
.stApp:has(.ms-home-marker) {{
    background: {COLORS['background']};
}}
.stApp:has(.ms-home-marker) header,
.stApp:has(.ms-home-marker) footer,
.stApp:has(.ms-home-marker) #MainMenu {{
    visibility: hidden;
}}
.stApp:has(.ms-home-marker) .block-container {{
    max-width: 920px;
    margin: 0 auto;
    padding-top: min(14vh, 7rem);
    padding-bottom: 4rem;
}}
.ms-home-hero {{
    text-align: center;
    margin-bottom: 3.5rem;
}}
.ms-home-kicker {{
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: {COLORS['text_muted']};
    margin-bottom: 1rem;
}}
.ms-home-accent-line {{
    width: 40px;
    height: 3px;
    margin: 0 auto 1.25rem auto;
    border-radius: 2px;
    background: linear-gradient(90deg, {COLORS['primary']}, {COLORS['secondary']});
}}
.ms-home-title {{
    margin: 0;
    font-size: clamp(2rem, 4.5vw, 2.85rem);
    font-weight: 700;
    letter-spacing: -0.045em;
    line-height: 1.12;
    color: {COLORS['text']};
}}
.ms-home-subtitle {{
    margin: 1rem auto 0 auto;
    max-width: 34rem;
    font-size: 1.05rem;
    font-weight: 400;
    line-height: 1.6;
    color: {COLORS['text_muted']};
}}
.ms-home-card {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 16px;
    padding: 1.5rem 1.35rem 1.25rem;
    height: 100%;
    min-height: 168px;
    display: flex;
    flex-direction: column;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    cursor: default;
}}
.ms-home-card:hover {{
    border-color: rgba(37, 99, 235, 0.35);
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}}
.ms-home-card-icon {{
    width: 40px;
    height: 40px;
    border-radius: 11px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 1rem;
}}
.ms-home-card-title {{
    font-size: 1.02rem;
    font-weight: 650;
    color: {COLORS['text']};
    margin-bottom: 0.35rem;
    letter-spacing: -0.02em;
}}
.ms-home-card-blurb {{
    font-size: 0.86rem;
    line-height: 1.55;
    color: {COLORS['text_muted']};
    flex: 1;
}}
.ms-home-footer {{
    text-align: center;
    margin-top: 3rem;
    font-size: 0.75rem;
    color: {COLORS['text_muted']};
    letter-spacing: 0.02em;
}}
.stApp:has(.ms-home-marker) .st-key-home_nav_obj button,
.stApp:has(.ms-home-marker) .st-key-home_nav_row button,
.stApp:has(.ms-home-marker) .st-key-home_nav_sch button {{
    background: transparent !important;
    color: {COLORS['primary']} !important;
    border: 1px solid {COLORS['border']} !important;
    font-weight: 600 !important;
    box-shadow: none !important;
    margin-top: 0.65rem;
    transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease !important;
}}
.stApp:has(.ms-home-marker) .st-key-home_nav_obj button:hover,
.stApp:has(.ms-home-marker) .st-key-home_nav_row button:hover,
.stApp:has(.ms-home-marker) .st-key-home_nav_sch button:hover {{
    background: {COLORS['muted']} !important;
    border-color: {COLORS['primary']} !important;
    transform: none !important;
    box-shadow: none !important;
}}
"""


OBJECT_EXPLORER_CSS = f"""
/* Object Explorer — 40/60 workspace, top/bottom stacks, no page scroll */
.stApp:has(.ms-oe-marker) section.main .block-container {{
    display: flex !important;
    flex-direction: column !important;
    height: calc(100vh - 5.5rem) !important;
    max-height: calc(100vh - 5.5rem) !important;
    overflow: hidden !important;
    padding-bottom: 1rem !important;
    box-sizing: border-box !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_page_header {{
    flex: 0 0 auto !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_workspace {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_workspace > div[data-testid="stVerticalBlock"] {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    height: 100% !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_workspace [data-testid="stHorizontalBlock"] {{
    align-items: stretch !important;
    height: 100% !important;
    min-height: 0 !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_workspace [data-testid="column"] {{
    height: 100% !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_workspace [data-testid="column"] > div {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
}}
/* Left / right columns — top strip + hero panel */
.stApp:has(.ms-oe-marker) .st-key-oe_left_column,
.stApp:has(.ms-oe-marker) .st-key-oe_right_column {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    height: 100% !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 0.75rem !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_left_column > div[data-testid="stVerticalBlock"],
.stApp:has(.ms-oe-marker) .st-key-oe_right_column > div[data-testid="stVerticalBlock"] {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    height: 100% !important;
    display: flex !important;
    flex-direction: column !important;
    gap: 0.75rem !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_connection_panel,
.stApp:has(.ms-oe-marker) .st-key-oe_search_panel {{
    flex: 0 0 auto !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_fleet_panel,
.stApp:has(.ms-oe-marker) .st-key-oe_results_panel {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_fleet_panel [data-testid="stVerticalBlockBorderWrapper"],
.stApp:has(.ms-oe-marker) .st-key-oe_results_panel [data-testid="stVerticalBlockBorderWrapper"] {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_fleet_panel [data-testid="stVerticalBlockBorderWrapper"] > div,
.stApp:has(.ms-oe-marker) .st-key-oe_results_panel [data-testid="stVerticalBlockBorderWrapper"] > div {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
}}
/* Compact search strip — horizontal match mode wraps on narrow widths */
.stApp:has(.ms-oe-marker) .st-key-oe_search_panel [data-testid="stRadio"] > div {{
    flex-wrap: wrap !important;
    gap: 0.35rem 0.75rem !important;
}}
/* Fleet table fills remaining panel height */
.stApp:has(.ms-oe-marker) .st-key-oe_fleet_table {{
    flex: 1 1 auto !important;
    min-height: 8rem !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_fleet_table > div {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    height: 100% !important;
    overflow: hidden !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_fleet_table [data-testid="stDataEditor"],
.stApp:has(.ms-oe-marker) .st-key-oe_fleet_table [data-testid="stDataFrame"] {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    max-height: 100% !important;
    overflow: auto !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_fleet_table [data-testid="stDataEditor"] > div,
.stApp:has(.ms-oe-marker) .st-key-oe_fleet_table [data-testid="stDataFrame"] > div {{
    max-height: 100% !important;
    min-height: 0 !important;
}}
/* Results: fixed summary + scrollable table */
.stApp:has(.ms-oe-marker) .st-key-oe_results_summary {{
    flex: 0 0 auto !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_results_table {{
    flex: 1 1 auto !important;
    min-height: 8rem !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_results_table > div {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    height: 100% !important;
    overflow: hidden !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_results_table [data-testid="stDataFrame"] {{
    flex: 1 1 auto !important;
    min-height: 0 !important;
    max-height: 100% !important;
    overflow: auto !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_results_table [data-testid="stDataFrame"] > div,
.stApp:has(.ms-oe-marker) .st-key-oe_results_table [data-testid="stDataFrame"] iframe {{
    max-height: 100% !important;
    min-height: 0 !important;
}}
/* Bordered inputs — username, password, object type, text to match */
.stApp:has(.ms-oe-marker) .st-key-username input,
.stApp:has(.ms-oe-marker) .st-key-password input,
.stApp:has(.ms-oe-marker) .st-key-oe_filter_text input {{
    border: 2px solid {COLORS['border']} !important;
    border-radius: 8px !important;
    background: {COLORS['surface']} !important;
    padding: 0.5rem 0.75rem !important;
}}
.stApp:has(.ms-oe-marker) .st-key-username input:focus,
.stApp:has(.ms-oe-marker) .st-key-password input:focus,
.stApp:has(.ms-oe-marker) .st-key-oe_filter_text input:focus {{
    border-color: {COLORS['primary']} !important;
    border-width: 2px !important;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12) !important;
    outline: none !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_object_type [data-testid="stSelectbox"] [data-baseweb="select"] > div,
.stApp:has(.ms-oe-marker) .st-key-oe_object_type [data-baseweb="select"] > div {{
    border: 2px solid {COLORS['border']} !important;
    border-radius: 8px !important;
    background: {COLORS['surface']} !important;
}}
.stApp:has(.ms-oe-marker) .st-key-oe_object_type [data-testid="stSelectbox"]:focus-within [data-baseweb="select"] > div,
.stApp:has(.ms-oe-marker) .st-key-oe_object_type [data-baseweb="select"]:focus-within > div {{
    border-color: {COLORS['primary']} !important;
    border-width: 2px !important;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12) !important;
}}
.ms-oe-panel-title {{
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: {COLORS['primary']};
    margin: 0 0 0.75rem 0;
}}
.ms-oe-empty {{
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1 1 auto;
    min-height: 0;
    color: {COLORS['text_muted']};
    font-size: 0.95rem;
    text-align: center;
    padding: 2rem;
}}
"""


def inject_global_styles(*, schema_compare: bool = False, home: bool = False, object_explorer: bool = False) -> None:
    """Inject design-system CSS once per run."""
    css = GLOBAL_CSS
    if schema_compare:
        css += SCHEMA_COMPARE_CSS
    if home:
        css += HOME_PAGE_CSS
    if object_explorer:
        css += OBJECT_EXPLORER_CSS
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def apply_page(
    *,
    title: str,
    icon: str = "",
    layout: str = "wide",
    sidebar_expanded: bool = False,
    schema_compare: bool = False,
    home: bool = False,
    object_explorer: bool = False,
) -> None:
    """Standard page bootstrap: config + global styles."""
    page_title = f"{icon} {title}".strip() if icon else title
    st.set_page_config(
        page_title=page_title,
        page_icon="🗄️",
        layout=layout,
        initial_sidebar_state="expanded" if sidebar_expanded else "collapsed",
    )
    inject_global_styles(schema_compare=schema_compare, home=home, object_explorer=object_explorer)
