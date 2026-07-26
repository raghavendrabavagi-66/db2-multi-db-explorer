"""Parse index DDL for structured summary comparison."""

from __future__ import annotations

import re

from ddl_normalizer import strip_comments_and_headers, strip_index_preamble

_INDEX_HEADER_RE = re.compile(
    r"CREATE\s+(?P<unique>UNIQUE\s+)?(?P<clustered>NONCLUSTERED\s+|CLUSTERED\s+)?INDEX\s+"
    r"(?P<index>\[[^\]]+\]|\w+)\s+ON\s+(?P<table>(?:\[[^\]]+\]|\w+)\.(?:\[[^\]]+\]|\w+))",
    re.IGNORECASE | re.DOTALL,
)
_COLUMN_RE = re.compile(
    r"\[([^\]]+)\]\s+(ASC|DESC)",
    re.IGNORECASE,
)


def _normalize_index_text(ddl: str) -> str:
    text = strip_comments_and_headers(ddl or "")
    text = strip_index_preamble(text)
    return re.sub(r"\s+", " ", text).strip()


def _index_kind(text: str) -> str:
    upper = text.upper()
    if "UNIQUE" in upper and "CREATE UNIQUE" in upper.replace("  ", " "):
        return "UNIQUE NONCLUSTERED"
    if re.search(r"CREATE\s+CLUSTERED\s+INDEX", upper):
        return "CLUSTERED"
    if re.search(r"CREATE\s+NONCLUSTERED\s+INDEX", upper):
        return "NONCLUSTERED"
    return "UNKNOWN"


def parse_index_ddl(ddl: str) -> dict[str, str | list[tuple[str, str]]]:
    """Extract comparable index properties from DDL text."""
    text = _normalize_index_text(ddl)
    if not text:
        return {"kind": "UNKNOWN"}

    header = _INDEX_HEADER_RE.search(text)
    if not header:
        return {"kind": "UNKNOWN", "ddl": text[:200]}

    cols_block_match = re.search(r"\(([^)]+)\)", text[header.end() :], re.DOTALL)
    columns: list[tuple[str, str]] = []
    if cols_block_match:
        for col_m in _COLUMN_RE.finditer(cols_block_match.group(1)):
            columns.append((col_m.group(1).upper(), col_m.group(2).upper()))

    return {
        "kind": _index_kind(text),
        "index": header.group("index").strip(),
        "table": header.group("table").strip(),
        "columns": columns,
    }


def _format_columns(columns: list[tuple[str, str]]) -> str:
    if not columns:
        return "—"
    return ", ".join(f"[{name}] {direction}" for name, direction in columns)


def index_summary_table(gitlab_ddl: str, db_ddl: str) -> list[dict[str, str]] | None:
    """Return property rows for index summary, or None if not parseable."""
    gl = parse_index_ddl(gitlab_ddl)
    db = parse_index_ddl(db_ddl)
    if gl.get("kind") == "UNKNOWN" and db.get("kind") == "UNKNOWN":
        return None

    rows: list[dict[str, str]] = []

    kind_gl = str(gl.get("kind", "—"))
    kind_db = str(db.get("kind", "—"))
    rows.append(
        {
            "Property": "Index kind",
            "GitLab": kind_gl,
            "Database": kind_db,
            "Match": "yes" if kind_gl == kind_db else "no",
        }
    )

    gl_cols = gl.get("columns") or []
    db_cols = db.get("columns") or []
    if isinstance(gl_cols, list) and isinstance(db_cols, list):
        rows.append(
            {
                "Property": "Key columns (summary)",
                "GitLab": _format_columns(gl_cols),
                "Database": _format_columns(db_cols),
                "Match": "yes" if gl_cols == db_cols else "no",
            }
        )
        all_names = sorted({n for n, _ in gl_cols} | {n for n, _ in db_cols})
        gl_map = dict(gl_cols)
        db_map = dict(db_cols)
        for name in all_names:
            gv = gl_map.get(name, "—")
            dv = db_map.get(name, "—")
            rows.append(
                {
                    "Property": f"  [{name}] sort",
                    "GitLab": gv,
                    "Database": dv,
                    "Match": "yes" if gv == dv else "no",
                }
            )

    return rows
