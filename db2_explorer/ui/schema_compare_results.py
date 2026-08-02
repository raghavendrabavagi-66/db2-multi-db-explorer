"""Schema Compare HTML fragments for stitch workspace injection."""

from __future__ import annotations

import html
from typing import Any, Literal

from db2_explorer.compare.schema_compare import (
    CompareStatusLiteral,
    ObjectCompareResult,
    SchemaCompareResult,
    flatten_results,
    redgate_status_label,
)
from db2_explorer.ddl.diff_viewer import prepare_display_ddl
from db2_explorer.gitlab.deployment_parser import OBJECT_TYPE_FILES

GroupByMode = Literal["difference", "object"]

_TYPE_LABELS = {
    "SCHEMA": "Schema",
    "SEQUENCE": "Sequence",
    "TABLE": "Table",
    "CONSTRAINT": "Constraint",
    "INDEX": "Index",
    "VIEW": "View",
    "FUNCTION": "Function",
    "PROCEDURE": "Procedure",
    "MQT_IMMEDIATE": "MQT Immediate",
    "MQT_DEFERRED": "MQT Deferred",
    "TRIGGER": "Trigger",
    "ROLE": "Role",
}

_GROUP_ORDER: list[tuple[CompareStatusLiteral, str, str]] = [
    ("different", "difference", "In both but different"),
    ("only_gitlab", "add_circle", "Only in GitLab"),
    ("only_db", "remove_circle", "Only in Azure"),
    ("identical", "check_circle", "Identical"),
]

_STATUS_ROW_ICON = {
    "different": "difference",
    "only_gitlab": "add_circle",
    "only_db": "remove_circle",
    "identical": "check_circle",
}


def comparison_summary_dict(result: SchemaCompareResult) -> dict[str, int]:
    s = result.summary
    return {
        "identical": s.identical,
        "different": s.different,
        "only_gitlab": s.only_gitlab,
        "only_db": s.only_db,
        "total": s.identical + s.different + s.only_gitlab + s.only_db,
    }


def _type_label(object_type: str) -> str:
    return _TYPE_LABELS.get(object_type, object_type.title())


def _diff_lines(text: str) -> list[str]:
    cleaned = prepare_display_ddl(text)
    if not cleaned.strip():
        return ["—"]
    return cleaned.splitlines() or ["—"]


def _stitch_diff_lines(lines: list[str], *, pane: str) -> str:
    parts: list[str] = []
    for idx, line in enumerate(lines, start=1):
        css = ""
        display = line
        if pane == "source" and line.startswith("- "):
            css = "diff-removed"
            display = line[2:]
        elif pane == "target" and line.startswith("+ "):
            css = "diff-added"
            display = line[2:]
        esc = html.escape(display)
        cls = f' class="flex {css}"' if css else ' class="flex"'
        parts.append(f'<div{cls}><span class="diff-line-num">{idx}</span>{esc}</div>')
    return "".join(parts)


def _build_stitch_diff_panes(gitlab_ddl: str, db_ddl: str) -> tuple[str, str]:
    left_lines = _diff_lines(gitlab_ddl)
    right_lines = _diff_lines(db_ddl)
    max_len = max(len(left_lines), len(right_lines))
    paired_left: list[str] = []
    paired_right: list[str] = []
    for i in range(max_len):
        left = left_lines[i] if i < len(left_lines) else ""
        right = right_lines[i] if i < len(right_lines) else ""
        if left != right:
            paired_left.append(f"- {left}" if left else "")
            paired_right.append(f"+ {right}" if right else "")
        else:
            paired_left.append(left)
            paired_right.append(right)
    return _stitch_diff_lines(paired_left, pane="source"), _stitch_diff_lines(paired_right, pane="target")


def _object_row_html(item: ObjectCompareResult, *, parent_group: str) -> str:
    icon = _STATUS_ROW_ICON.get(item.status, "help")
    type_label = _type_label(item.object_type)
    src_schema = html.escape(item.schema or "—")
    src_name = html.escape(item.name or "—")
    tgt_schema = html.escape(item.schema or "—")
    tgt_name = html.escape(item.name or "—")
    key = html.escape(item.object_key, quote=True)
    group_key = html.escape(parent_group, quote=True)
    status = html.escape(item.status, quote=True)
    obj_type = html.escape(item.object_type, quote=True)
    return (
        f'<tr class="border-b border-outline-variant hover:bg-surface-container-low transition-colors sc-object-row sc-group-member" '
        f'data-object-key="{key}" data-parent-group="{group_key}" data-status="{status}" data-object-type="{obj_type}">'
        f'<td class="px-md py-2"><div class="flex items-center gap-xs">'
        f'<span class="material-symbols-outlined text-tertiary text-[18px]">{icon}</span>'
        f'<span class="text-secondary">{html.escape(type_label)}</span></div></td>'
        f'<td class="px-md py-2 font-medium text-right text-secondary">{src_schema}</td>'
        f'<td class="px-md py-2 font-medium text-right">{src_name}</td>'
        f'<td class="px-xs py-2 text-center flex justify-center">'
        f'<input class="rounded border-outline-variant text-primary focus:ring-primary sc-row-check" type="checkbox"></td>'
        f'<td class="px-md py-2 font-medium">{tgt_name}</td>'
        f'<td class="px-md py-2 text-secondary text-left">{tgt_schema}</td>'
        f'<td class="px-md py-2 text-secondary text-left">—</td>'
        f"</tr>"
    )


def _group_header_html(group_key: str, label: str, count: int, *, expanded: bool = True) -> str:
    chevron = "expand_more" if expanded else "chevron_right"
    expanded_attr = "true" if expanded else "false"
    return (
        f'<tr class="bg-surface-container-high/50 group cursor-pointer hover:bg-surface-container-high transition-colors sc-group-row" '
        f'data-group-key="{html.escape(group_key, quote=True)}" data-expanded="{expanded_attr}">'
        f'<td class="px-md py-2 border-b border-outline-variant font-bold text-on-surface text-center" colspan="7">'
        f'<div class="flex items-center justify-between w-full">'
        f'<div class="flex items-center w-full"><div class="flex items-center gap-sm w-[33%]">'
        f'<span class="material-symbols-outlined text-primary sc-group-chevron">{chevron}</span>'
        f"<span>{count} {html.escape(label)}</span></div>"
        f'<div class="w-12 flex justify-center"><span class="text-body-sm font-medium text-secondary">0 of {count}</span></div>'
        f'<div class="w-12 flex justify-center">'
        f'<input type="checkbox" class="rounded border-outline-variant text-primary focus:ring-primary" title="Select Group"></div>'
        f'<div class="flex-grow"></div></div></div></td></tr>'
    )


def _object_type_sort_keys(present: set[str] | None = None) -> list[str]:
    known = list(OBJECT_TYPE_FILES.keys())
    if not present:
        return known
    return known + sorted(present - set(known))


def comparison_table_group_config() -> dict[str, Any]:
    """JSON-serializable grouping metadata for workspace iframe JS."""
    return {
        "differenceGroups": [
            {"key": status, "label": label} for status, _icon, label in _GROUP_ORDER
        ],
        "objectTypeOrder": list(OBJECT_TYPE_FILES.keys()),
        "typeLabels": dict(_TYPE_LABELS),
        "statusIcons": dict(_STATUS_ROW_ICON),
    }


def comparison_table_html(
    result: SchemaCompareResult,
    *,
    group_by: GroupByMode = "difference",
) -> str:
    """Grouped comparison table body rows matching stitch 07 layout."""
    flat = flatten_results(result)
    if not flat:
        return (
            '<tr><td colspan="7" class="px-md py-lg text-center text-secondary">'
            "No objects compared yet.</td></tr>"
        )

    parts: list[str] = []
    if group_by == "object":
        by_type: dict[str, list[ObjectCompareResult]] = {}
        for item in flat:
            by_type.setdefault(item.object_type, []).append(item)
        for object_type in _object_type_sort_keys(set(by_type.keys())):
            items = by_type.get(object_type, [])
            if not items:
                continue
            parts.append(_group_header_html(object_type, _type_label(object_type), len(items)))
            for item in items:
                parts.append(_object_row_html(item, parent_group=object_type))
    else:
        by_status: dict[CompareStatusLiteral, list[ObjectCompareResult]] = {
            "different": [],
            "only_gitlab": [],
            "only_db": [],
            "identical": [],
        }
        for item in flat:
            by_status.setdefault(item.status, []).append(item)
        for status, _icon, label in _GROUP_ORDER:
            items = by_status.get(status, [])
            if not items:
                continue
            parts.append(_group_header_html(status, label, len(items)))
            for item in items:
                parts.append(_object_row_html(item, parent_group=status))
    return "".join(parts)


def build_objects_map(result: SchemaCompareResult) -> dict[str, dict[str, Any]]:
    objects: dict[str, dict[str, Any]] = {}
    for item in flatten_results(result):
        src_html, tgt_html = _build_stitch_diff_panes(item.gitlab_ddl, item.db_ddl)
        src_file = item.source_file or OBJECT_TYPE_FILES.get(item.object_type, "—")
        objects[item.object_key] = {
            "object_key": item.object_key,
            "object_type": item.object_type,
            "type_label": _type_label(item.object_type),
            "schema": item.schema,
            "name": item.name,
            "parent": item.parent or "",
            "status": item.status,
            "status_label": redgate_status_label(item.status),
            "source_file": src_file,
            "gitlab_line": item.gitlab_line,
            "diff_source_html": src_html,
            "diff_target_html": tgt_html,
            "summary_html": (
                f"<p><strong>Status:</strong> {html.escape(redgate_status_label(item.status))}</p>"
                f"<p><strong>Type:</strong> {html.escape(_type_label(item.object_type))}</p>"
                f"<p><strong>Schema:</strong> {html.escape(item.schema)}</p>"
                f"<p><strong>Object:</strong> {html.escape(item.name)}</p>"
                f"<p><strong>Source file:</strong> {html.escape(src_file)}</p>"
            ),
        }
    return objects
