"""Parse constraint DDL for structured summary comparison."""

from __future__ import annotations

import re

from ddl_normalizer import strip_comments_and_headers

_ACTION = r"(CASCADE|NO\s+ACTION|SET\s+NULL|SET\s+DEFAULT)"
_FK_RE = re.compile(
    rf"FOREIGN\s+KEY\s*\((?P<parent_cols>[^)]+)\)\s*REFERENCES\s+"
    rf"(?P<ref_table>(?:\[[^\]]+\]\.)?\[[^\]]+\]|[^\s(]+)\s*"
    rf"\((?P<ref_cols>[^)]+)\)"
    rf"(?:\s*ON\s+DELETE\s+(?P<on_delete>{_ACTION}))?"
    rf"(?:\s*ON\s+UPDATE\s+(?P<on_update>{_ACTION}))?",
    re.IGNORECASE | re.DOTALL,
)
_PK_RE = re.compile(
    r"PRIMARY\s+KEY\s*\((?P<cols>[^)]+)\)",
    re.IGNORECASE,
)
_CHECK_RE = re.compile(
    r"CHECK\s+(?P<definition>.+?)\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _clean_action(value: str | None) -> str:
    if not value:
        return "NO ACTION"
    return re.sub(r"\s+", " ", value.strip().upper())


def _one_line(ddl: str) -> str:
    text = strip_comments_and_headers(ddl or "")
    return re.sub(r"\s+", " ", text).strip()


def parse_constraint_ddl(ddl: str) -> dict[str, str]:
    """Extract comparable constraint properties from DDL text."""
    line = _one_line(ddl)
    if not line:
        return {"kind": "UNKNOWN"}

    fk = _FK_RE.search(line)
    if fk:
        return {
            "kind": "FOREIGN KEY",
            "parent_columns": fk.group("parent_cols").strip(),
            "referenced_table": fk.group("ref_table").strip(),
            "referenced_columns": fk.group("ref_cols").strip(),
            "on_delete": _clean_action(fk.group("on_delete")),
            "on_update": _clean_action(fk.group("on_update")),
        }

    pk = _PK_RE.search(line)
    if pk:
        return {
            "kind": "PRIMARY KEY",
            "columns": pk.group("cols").strip(),
        }

    chk = _CHECK_RE.search(line)
    if chk:
        return {
            "kind": "CHECK",
            "definition": chk.group("definition").strip(),
        }

    return {"kind": "UNKNOWN", "ddl": line[:200]}


def fk_summary_table(gitlab_ddl: str, db_ddl: str) -> list[dict[str, str]] | None:
    """Return property rows for FK summary, or None if not a foreign key."""
    gl = parse_constraint_ddl(gitlab_ddl)
    db = parse_constraint_ddl(db_ddl)
    if gl.get("kind") != "FOREIGN KEY" and db.get("kind") != "FOREIGN KEY":
        return None

    props = [
        ("Constraint kind", "kind"),
        ("Parent columns", "parent_columns"),
        ("Referenced table", "referenced_table"),
        ("Referenced columns", "referenced_columns"),
        ("On DELETE", "on_delete"),
        ("On UPDATE", "on_update"),
    ]
    rows: list[dict[str, str]] = []
    for label, key in props:
        gv = gl.get(key, "—") or "—"
        dv = db.get(key, "—") or "—"
        match = "yes" if gv == dv else "no"
        rows.append(
            {
                "Property": label,
                "GitLab": gv,
                "Database": dv,
                "Match": match,
            }
        )
    return rows
