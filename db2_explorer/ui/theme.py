"""Global Streamlit theme — delegates visual shell to stitch_exports HTML + Tailwind."""

from __future__ import annotations

import streamlit as st

from db2_explorer.ui.stitch_shell import _token_fallback_css, bootstrap_stitch, streamlit_chrome_css
from db2_explorer.ui.studio_tokens import COLORS

__all__ = ["COLORS", "apply_page", "inject_global_styles"]


def inject_global_styles(*, home: bool = False, object_explorer: bool = False, **_kwargs) -> None:
    if home or object_explorer:
        return  # Shell reset + Tailwind injected from stitch iframe <head> scripts.
    bootstrap_stitch()
    st.markdown(
        f"<style>{streamlit_chrome_css()}\n{_token_fallback_css()}</style>",
        unsafe_allow_html=True,
    )


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
    page_title = f"{icon} {title}".strip() if icon else title
    st.set_page_config(
        page_title=page_title,
        page_icon="🗄️",
        layout=layout,
        initial_sidebar_state="expanded" if sidebar_expanded else "collapsed",
    )
    inject_global_styles(home=home, object_explorer=object_explorer)
