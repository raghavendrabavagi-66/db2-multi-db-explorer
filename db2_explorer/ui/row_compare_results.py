"""Row Compare result table HTML — shared by Streamlit page and background API."""

from __future__ import annotations

import html
import math
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


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return True
    return False


def format_count_value(value: Any) -> str:
    """Render row counts without spurious float precision (``767.0`` → ``767``)."""
    if _is_missing(value):
        return "N/A"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number) or math.isinf(number):
        return "N/A"
    if number == int(number):
        return str(int(number))
    return str(number).rstrip("0").rstrip(".")


def format_delta_value(value: Any) -> str:
    """Render delta; prefix positives with ``+`` (e.g. target-only → ``+94``)."""
    if _is_missing(value):
        return "N/A"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(number) or math.isinf(number):
        return "N/A"
    if number == int(number):
        whole = int(number)
        if whole > 0:
            return f"+{whole}"
        return str(whole)
    text = str(number).rstrip("0").rstrip(".")
    if number > 0 and not text.startswith("+"):
        return f"+{text}"
    return text


def comparison_rows_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return (
            '<tr><td colspan="5" class="px-md py-4 text-center text-secondary font-body-sm">'
            "No comparison results yet. Click RUN COMPARISON.</td></tr>"
        )
    parts: list[str] = []
    for row in rows:
        name = html.escape(str(row.get("Table Name") or row.get("Table") or ""))
        src_s = html.escape(format_count_value(row.get("Source Count")))
        tgt_s = html.escape(format_count_value(row.get("Target Count")))
        delta_s = html.escape(format_delta_value(row.get("Delta")))
        badge = status_badge_html(str(row.get("Status", "")))
        parts.append(
            f'<tr class="hover:bg-surface-container transition-colors">'
            f'<td class="px-md py-2 font-code-sm text-xs text-on-surface">{name}</td>'
            f'<td class="px-md py-2 text-right">{src_s}</td>'
            f'<td class="px-md py-2 text-right">{tgt_s}</td>'
            f'<td class="px-md py-2 text-right">{delta_s}</td>'
            f'<td class="px-md py-2">{badge}</td></tr>'
        )
    return "".join(parts)
