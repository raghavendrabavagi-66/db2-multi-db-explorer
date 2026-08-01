"""Object Explorer search results — shared HTML/stats helpers."""

from __future__ import annotations

import html
from typing import Any

from db2_explorer.clients.db2 import DBResult


def empty_results_row_html() -> str:
    return (
        '<tr><td colspan="7" class="px-md py-10 text-center text-secondary text-sm">'
        "Run a search to see catalog objects across your fleet.</td></tr>"
    )


def results_tbody_rows(results: list[DBResult], *, matches_only: bool) -> str:
    rows: list[str] = []
    for res in results:
        c = res.connection
        if res.rows:
            for row in res.rows:
                if matches_only and not row.get("Object Name"):
                    continue
                name = html.escape(str(row.get("Object Name") or "—"))
                schema = html.escape(str(row.get("Schema") or "—"))
                status = res.status if res.ok else "error"
                badge = (
                    "bg-emerald-100 text-emerald-700"
                    if res.ok
                    else "bg-red-100 text-red-700"
                )
                row_cls = "" if res.ok else ' class="bg-red-50 hover:bg-red-100 transition-colors group"'
                rows.append(
                    f"<tr{row_cls}>"
                    f'<td class="px-md py-2 font-code-sm text-xs">{html.escape(c.dbname)}</td>'
                    f'<td class="px-md py-2 font-code-sm text-xs">{html.escape(c.host)}</td>'
                    f'<td class="px-md py-2 font-code-sm text-xs text-primary">{schema}</td>'
                    f'<td class="px-md py-2 font-code-sm text-xs font-bold">{name}</td>'
                    f'<td class="px-md py-2 text-xs">{html.escape(str(row.get("Object Type") or ""))}</td>'
                    f'<td class="px-md py-2 text-[10px] text-secondary">'
                    f'{html.escape(str(row.get("Create Time") or "—"))}</td>'
                    f'<td class="px-md py-2"><span class="inline-flex items-center px-1.5 py-0.5 '
                    f'rounded text-[10px] font-bold {badge}">{html.escape(status.upper())}</span></td>'
                    f"</tr>"
                )
        elif not matches_only:
            badge = "bg-red-100 text-red-700" if not res.ok else "bg-emerald-100 text-emerald-700"
            label = res.status.upper() if not res.ok else "OK"
            rows.append(
                f'<tr class="bg-red-50 hover:bg-red-100 transition-colors group">'
                f'<td class="px-md py-2 font-code-sm text-xs">{html.escape(c.dbname)}</td>'
                f'<td class="px-md py-2 font-code-sm text-xs">{html.escape(c.host)}</td>'
                f'<td class="px-md py-2 font-code-sm text-xs">—</td>'
                f'<td class="px-md py-2 font-code-sm text-xs">—</td>'
                f'<td class="px-md py-2 text-xs">—</td>'
                f'<td class="px-md py-2 text-[10px] text-secondary">—</td>'
                f'<td class="px-md py-2"><span class="inline-flex items-center px-1.5 py-0.5 '
                f'rounded text-[10px] font-bold {badge}">{html.escape(label)}</span></td></tr>'
            )
    if not rows:
        return empty_results_row_html()
    return "\n".join(rows)


def results_stats(
    results: list[DBResult] | None,
    *,
    object_type: str,
    operator: str,
    filter_text: str,
    last_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not results:
        return {
            "scanned": 0,
            "reachable": 0,
            "failed": 0,
            "matched_dbs": 0,
            "total_objects": 0,
            "filter_line": "No search run yet",
            "scan_time_s": None,
            "status_line": "Ready",
            "connected_label": "Connected: —",
        }

    ok = [r for r in results if r.ok]
    failed = [r for r in results if r.status in ("unreachable", "error")]
    matched_dbs = [r for r in ok if r.match_count > 0]
    total_objects = sum(r.match_count for r in ok)
    meta = last_meta or {}
    ft = meta.get("text", filter_text) or "any"
    filter_line = (
        f'{meta.get("object_type", object_type)} · '
        f'{meta.get("operator", operator)} · '
        f'"{ft}"'
    )
    scan_ms = meta.get("scan_time_ms")
    if scan_ms is None:
        scan_ms = sum(r.elapsed_ms for r in results)
    scan_time_s = scan_ms / 1000.0 if scan_ms else None

    if failed and not ok:
        status_line = "All systems unreachable"
    elif failed:
        status_line = f"{len(failed)} database(s) failed"
    else:
        status_line = "All systems operational"

    return {
        "scanned": len(results),
        "reachable": len(ok),
        "failed": len(failed),
        "matched_dbs": len(matched_dbs),
        "total_objects": total_objects,
        "filter_line": filter_line,
        "scan_time_s": scan_time_s,
        "status_line": status_line,
        "connected_label": f"Connected: {len(ok)} database(s)",
    }


def search_response_payload(
    results: list[DBResult],
    *,
    object_type: str,
    operator: str,
    filter_text: str,
    last_meta: dict[str, Any],
) -> dict[str, Any]:
    stats = results_stats(
        results,
        object_type=object_type,
        operator=operator,
        filter_text=filter_text,
        last_meta=last_meta,
    )
    scan_label = (
        f"Scan Time: {stats['scan_time_s']:.2f}s"
        if stats["scan_time_s"] is not None
        else "Scan Time: —"
    )
    return {
        "ok": True,
        "error": "",
        "stats": stats,
        "scan_time_label": scan_label,
        "tbody_html_all": results_tbody_rows(results, matches_only=False),
        "tbody_html_matches": results_tbody_rows(results, matches_only=True),
    }
