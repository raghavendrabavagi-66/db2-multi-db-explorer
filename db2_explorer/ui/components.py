"""Reusable Streamlit layout components."""

from __future__ import annotations

import streamlit as st

from db2_explorer.ui.theme import COLORS


def sidebar_brand(*, tagline: str = "Enterprise migration intelligence") -> None:
    """Branded sidebar header."""
    st.markdown(
        f"""
        <div style="padding: 0.5rem 0 1.25rem 0;">
            <div style="font-size: 1.35rem; font-weight: 700; color: #f8fafc;
                        letter-spacing: -0.02em;">DB2 Migration Studio</div>
            <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 0.25rem;
                        line-height: 1.4;">{tagline}</div>
            <div style="height: 3px; width: 48px; margin-top: 0.75rem;
                        background: linear-gradient(90deg, {COLORS['accent']}, {COLORS['secondary']});
                        border-radius: 2px;"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(
    title: str,
    subtitle: str = "",
    *,
    badge: str = "",
) -> None:
    """Premium page title block."""
    badge_html = (
        f'<span style="display:inline-block;margin-left:0.5rem;padding:0.15rem 0.55rem;'
        f'font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:0.06em;'
        f'background:{COLORS["muted"]};color:{COLORS["primary"]};border-radius:999px;">'
        f"{badge}</span>"
        if badge
        else ""
    )
    sub = (
        f'<p style="margin:0.35rem 0 0 0;color:{COLORS["text_muted"]};'
        f'font-size:1.02rem;line-height:1.5;max-width:720px;">{subtitle}</p>'
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div style="margin-bottom: 1.25rem;">
            <h1 style="margin:0;font-size:1.85rem;font-weight:700;color:{COLORS['primary_dark']};
                       letter-spacing:-0.03em;line-height:1.2;">
                {title}{badge_html}
            </h1>
            {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )


def feature_card(
    title: str,
    description: str,
    *,
    icon_svg: str,
    accent: str | None = None,
) -> None:
    """Service card for the home page."""
    accent = accent or COLORS["primary"]
    st.markdown(
        f"""
        <div class="ms-feature-card" style="
            background: {COLORS['surface']};
            border: 1px solid {COLORS['border']};
            border-radius: 16px;
            padding: 1.35rem 1.25rem;
            height: 100%;
            box-shadow: 0 1px 3px rgba(15,23,42,0.06);
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        ">
            <div style="width:44px;height:44px;border-radius:12px;
                        background: linear-gradient(135deg, {accent}22, {accent}11);
                        display:flex;align-items:center;justify-content:center;
                        margin-bottom:0.85rem;color:{accent};">
                {icon_svg}
            </div>
            <div style="font-size:1.05rem;font-weight:650;color:{COLORS['primary_dark']};
                        margin-bottom:0.4rem;">{title}</div>
            <div style="font-size:0.88rem;color:{COLORS['text_muted']};line-height:1.55;">
                {description}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_card(title: str, *, help_text: str = "") -> None:
    """Visual section divider."""
    help_html = (
        f'<span style="font-weight:400;color:{COLORS["text_muted"]};font-size:0.85rem;">'
        f" — {help_text}</span>"
        if help_text
        else ""
    )
    st.markdown(
        f"""
        <div style="margin: 1.5rem 0 0.75rem 0; padding-bottom: 0.35rem;
                    border-bottom: 2px solid {COLORS['border']};">
            <span style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
                         letter-spacing: 0.08em; color: {COLORS['accent']};">Section</span>
            <div style="font-size: 1.1rem; font-weight: 650; color: {COLORS['primary_dark']};">
                {title}{help_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_strip(metrics: list[tuple[str, str | int, str | None]]) -> None:
    """Row of KPI metrics: (label, value, delta_optional)."""
    cols = st.columns(len(metrics))
    for col, (label, value, delta) in zip(cols, metrics):
        with col:
            if delta is not None:
                st.metric(label, value, delta)
            else:
                st.metric(label, value)


def status_banner(message: str, *, kind: str = "info") -> None:
    """Inline status strip."""
    palette = {
        "info": (COLORS["muted"], COLORS["primary"]),
        "success": ("#D1FAE5", COLORS["success"]),
        "warn": ("#FEF3C7", COLORS["accent"]),
    }
    bg, fg = palette.get(kind, palette["info"])
    st.markdown(
        f"""
        <div style="background:{bg};color:{fg};padding:0.65rem 1rem;border-radius:10px;
                    font-size:0.9rem;margin-bottom:0.75rem;border-left:4px solid {fg};">
            {message}
        </div>
        """,
        unsafe_allow_html=True,
    )


def redgate_comparison_bar(
    counts: dict[str, int],
    *,
    active_bucket: str,
    session_key: str = "sch_status_bucket",
) -> None:
    """Redgate-style clickable comparison summary (status buckets)."""
    bucket_specs: list[tuple[str, str, str, str]] = [
        ("drift", "Needs attention", str(counts.get("drift", 0)), COLORS["accent"]),
        ("identical", "In both — identical", str(counts.get("identical", 0)), COLORS["success"]),
        ("different", "In both — different", str(counts.get("different", 0)), "#EA580C"),
        ("only_gitlab", "Only in GitLab", str(counts.get("only_gitlab", 0)), COLORS["primary"]),
        ("only_db", "Only in database", str(counts.get("only_db", 0)), "#7C3AED"),
    ]
    cols = st.columns(len(bucket_specs))
    for col, (bucket_id, label, value, accent) in zip(cols, bucket_specs):
        with col:
            is_active = active_bucket == bucket_id
            st.markdown(
                f"""
                <div style="
                    border: 2px solid {accent if is_active else COLORS['border']};
                    border-radius: 12px;
                    padding: 0.65rem 0.75rem;
                    background: {accent + '14' if is_active else COLORS['surface']};
                    margin-bottom: 0.35rem;
                ">
                    <div style="font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
                                letter-spacing: 0.06em; color: {COLORS['text_muted']};">
                        {label}
                    </div>
                    <div style="font-size: 1.65rem; font-weight: 700; color: {accent};
                                line-height: 1.2; margin-top: 0.15rem;">
                        {value}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "Show" if not is_active else "Showing",
                key=f"sch_bucket_{bucket_id}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
                disabled=is_active,
            ):
                st.session_state[session_key] = bucket_id
                st.rerun()


# SVG icons (Lucide-style, no emoji per design checklist)
ICON_SEARCH = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>'
ICON_COMPARE = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 3h5v5M4 20 21 3M21 16v5h-5M15 15l6 6M4 4l5 5"/></svg>'
ICON_SCHEMA = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></svg>'
