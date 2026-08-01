"""Studio Precision shared layout — matches stitch_exports HTML structure."""

from __future__ import annotations

import streamlit as st

from db2_explorer.ui.studio_tokens import COLORS

C = COLORS


def page_marker(page: str) -> None:
    st.markdown(
        f'<div class="ms-studio-marker ms-studio-{page}" aria-hidden="true" style="display:none;"></div>',
        unsafe_allow_html=True,
    )


def _nav_link(label: str, href: str | None, *, active: bool) -> str:
    if active:
        return (
            f'<span class="studio-nav-link studio-nav-active">{label}</span>'
        )
    if href:
        return f'<a class="studio-nav-link" href="{href}" target="_self">{label}</a>'
    return f'<span class="studio-nav-link studio-nav-disabled">{label}</span>'


def top_nav(*, active: str = "home") -> None:
    """Top navigation bar — stitch home / object explorer pattern."""
    items = [
        ("home", "Home", "app.py"),
        ("projects", "Projects", None),
        ("migrations", "Migrations", None),
        ("monitoring", "Monitoring", None),
        ("settings", "Settings", None),
    ]
    links = "".join(_nav_link(lbl, href, active=(key == active)) for key, lbl, href in items)
    st.markdown(
        f"""
        <nav class="studio-topnav">
          <div class="studio-topnav-left">
            <span class="studio-brand">DB2 Migration Studio</span>
            <div class="studio-nav-links">{links}</div>
          </div>
          <div class="studio-topnav-right">
            <span class="material-symbols-outlined studio-icon-btn">notifications</span>
            <span class="material-symbols-outlined studio-icon-btn">help_outline</span>
            <span class="material-symbols-outlined studio-icon-btn">account_circle</span>
            <span class="studio-deploy-btn">Deploy</span>
          </div>
        </nav>
        """,
        unsafe_allow_html=True,
    )


def service_header(title: str, *, tagline: str = "", show_divider: bool = True) -> None:
    """Object Explorer style header extension below top nav."""
    divider = (
        '<span class="studio-header-divider"></span>' if show_divider else ""
    )
    tagline_html = (
        f'<span class="studio-service-tagline">{tagline}</span>' if tagline else ""
    )
    st.markdown(
        f"""
        <div class="studio-service-header">
          {divider}
          <div class="studio-service-titles">
            <span class="studio-service-title">{title}</span>
            {tagline_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sub_toolbar(
    *,
    back_label: str = "Home",
    back_page: str = "app.py",
    left_stats: list[tuple[str, str]] | None = None,
) -> None:
    """Breadcrumb toolbar below nav (Object Explorer stitch screen)."""
    stats_html = ""
    if left_stats:
        parts = []
        for icon, text in left_stats:
            parts.append(
                f'<span class="studio-sub-stat">'
                f'<span class="material-symbols-outlined studio-sub-stat-icon">{icon}</span>'
                f"{text}</span>"
            )
        stats_html = f'<div class="studio-sub-stats">{"".join(parts)}</div>'

    st.markdown(
        f"""
        <div class="studio-sub-toolbar">
          <a class="studio-back-link" href="{back_page}" target="_self">
            <span class="material-symbols-outlined">arrow_back</span>{back_label}
          </a>
          {stats_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def workspace_toolbar(
    *,
    left_actions: list[tuple[str, str, str]] | None = None,
    show_search: bool = False,
    search_placeholder: str = "Search objects...",
    right_primary: tuple[str, str] | None = None,
) -> None:
    """Secondary toolbar for Row/Schema compare workspace screens."""
    left_html = ""
    if left_actions:
        btns = []
        for icon, label, _key in left_actions:
            btns.append(
                f'<span class="studio-ws-tool-btn">'
                f'<span class="material-symbols-outlined">{icon}</span>{label}</span>'
            )
        left_html = f'<div class="studio-ws-tool-left">{"".join(btns)}</div>'

    right_html = ""
    if show_search:
        right_html += (
            f'<div class="studio-ws-search">'
            f'<span class="material-symbols-outlined">search</span>'
            f'<span class="studio-ws-search-ph">{search_placeholder}</span></div>'
        )
    if right_primary:
        _icon, label = right_primary
        right_html += f'<span class="studio-ws-primary-btn">{label}</span>'

    st.markdown(
        f"""
        <div class="studio-ws-toolbar">
          {left_html}
          <div class="studio-ws-tool-right">{right_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def panel_label(text: str, *, uppercase: bool = True) -> None:
    cls = "studio-panel-label"
    if uppercase:
        cls += " studio-upper"
    st.markdown(f'<p class="{cls}">{text}</p>', unsafe_allow_html=True)


def hero_panel_open(key: str = "") -> None:
    """Visual hero panel wrapper — use with st.container inside."""
    extra = f' data-panel-key="{key}"' if key else ""
    st.markdown(f'<div class="studio-hero-panel"{extra}>', unsafe_allow_html=True)


def hero_panel_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def home_hero() -> None:
    st.markdown(
        f"""
        <section class="studio-home-hero">
          <span class="studio-kicker">Migration Intelligence</span>
          <h1 class="studio-home-title">DB2 Migration Studio</h1>
          <p class="studio-home-subtitle">
            Select a professional workflow to begin your migration journey. Our platform
            automates schema conversion and data validation for enterprise-grade deployments.
          </p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def home_card(
    title: str,
    blurb: str,
    *,
    icon: str,
    icon_bg: str,
    icon_color: str,
) -> None:
    st.markdown(
        f"""
        <div class="studio-home-card">
          <div class="studio-home-card-icon" style="background:{icon_bg};color:{icon_color};">
            <span class="material-symbols-outlined">{icon}</span>
          </div>
          <h3 class="studio-home-card-title">{title}</h3>
          <p class="studio-home-card-blurb">{blurb}</p>
          <div class="studio-home-card-enter">
            Enter <span class="material-symbols-outlined">arrow_forward</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def home_footer() -> None:
    st.markdown(
        """
        <footer class="studio-home-footer">
          <span class="studio-footer-item">
            DB2 LUW <span class="material-symbols-outlined">arrow_forward</span> Azure SQL
          </span>
          <span class="studio-footer-dot"></span>
          <span>GitLab deployment validation</span>
        </footer>
        """,
        unsafe_allow_html=True,
    )


def metric_strip_html(metrics: list[tuple[str, str, str | None]]) -> str:
    """Build metric row HTML: (label, value, accent_border_color|None)."""
    cells = []
    for label, value, accent in metrics:
        border = f' style="border-left:4px solid {accent};"' if accent else ""
        cells.append(
            f'<div class="studio-metric-cell"{border}>'
            f'<span class="studio-metric-label">{label}</span>'
            f'<span class="studio-metric-value">{value}</span></div>'
        )
    return f'<div class="studio-metric-strip">{"".join(cells)}</div>'


def status_badge(status: str) -> str:
    s = status.lower()
    if s in ("ok", "reachable", "identical", "match", "matched"):
        cls, label = "studio-badge-ok", status.upper()
    elif s in ("error", "failed", "unreachable"):
        cls, label = "studio-badge-err", status.upper()
    elif s in ("warning", "mismatch", "different"):
        cls, label = "studio-badge-warn", status.upper()
    else:
        cls, label = "studio-badge-neutral", status
    return f'<span class="studio-badge {cls}">{label}</span>'


def setup_modal_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="studio-modal-header">
          <div>
            <h2 class="studio-modal-title">{title}</h2>
            <p class="studio-modal-subtitle">{subtitle}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def source_target_columns_header(left_title: str, left_sub: str, left_icon: str,
                                  right_title: str, right_sub: str, right_icon: str) -> None:
    lc, rc = st.columns(2)
    with lc:
        st.markdown(
            f"""
            <div class="studio-source-header">
              <div class="studio-source-icon"><span class="material-symbols-outlined">{left_icon}</span></div>
              <div><div class="studio-source-title">{left_title}</div>
              <div class="studio-source-sub">{left_sub}</div></div>
            </div>""",
            unsafe_allow_html=True,
        )
    with rc:
        st.markdown(
            f"""
            <div class="studio-source-header">
              <div class="studio-source-icon studio-source-icon-alt">
                <span class="material-symbols-outlined">{right_icon}</span></div>
              <div><div class="studio-source-title">{right_title}</div>
              <div class="studio-source-sub">{right_sub}</div></div>
            </div>""",
            unsafe_allow_html=True,
        )
