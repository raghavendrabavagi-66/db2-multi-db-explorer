"""Row Compare result table HTML — shared by Streamlit page and background API."""

from __future__ import annotations

import html
from typing import Any


def status_badge_html(status: str) -> str:
    s = (status or "").upper()
    if s == "MATCH":
        return (
            '<span class="bg-emerald-100 text-emerald-700 px-sm py-0.5 rounded '
            'text-[10px] font-bold tracking-wider">MATCH</span>'
        )
    if s in {"MISMATCH", "DELTA"}:
        return (
            '<span class="bg-amber-100 text-amber-700 px-sm py-0.5 rounded '
            'text-[10px] font-bold tracking-wider">MISMATCH</span>'
        )
    return (
        '<span class="bg-red-100 text-red-700 px-sm py-0.5 rounded '
        'text-[10px] font-bold tracking-wider">FAILED</span>'
    )


def comparison_rows_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return (
            '<tr><td colspan="5" class="px-md py-4 text-center text-secondary font-body-sm">'
            "No comparison results yet. Click RUN COMPARISON.</td></tr>"
        )
    parts: list[str] = []
    for row in rows:
        name = html.escape(str(row.get("Table Name") or row.get("Table") or ""))
        src = row.get("Source Count", "N/A")
        tgt = row.get("Target Count", "N/A")
        delta = row.get("Delta", "N/A")
        badge = status_badge_html(str(row.get("Status", "")))
        src_s = html.escape(str(src))
        tgt_s = html.escape(str(tgt))
        delta_s = html.escape(str(delta))
        parts.append(
            f'<tr class="hover:bg-surface-container transition-colors">'
            f'<td class="px-md py-2 font-code-sm text-xs text-on-surface">{name}</td>'
            f'<td class="px-md py-2 text-right">{src_s}</td>'
            f'<td class="px-md py-2 text-right">{tgt_s}</td>'
            f'<td class="px-md py-2 text-right">{delta_s}</td>'
            f'<td class="px-md py-2">{badge}</td></tr>'
        )
    return "".join(parts)
