"""Normalize DDL text before comparison."""

from __future__ import annotations

import re

_SQL_KEYWORDS = {
    "ALTER", "TABLE", "ADD", "CONSTRAINT", "PRIMARY", "KEY", "FOREIGN", "REFERENCES",
    "ON", "DELETE", "UPDATE", "CASCADE", "NO", "ACTION", "CHECK", "CREATE", "SCHEMA",
    "INDEX", "UNIQUE", "NONCLUSTERED", "CLUSTERED", "PROCEDURE", "FUNCTION", "VIEW",
    "TRIGGER", "ROLE", "SEQUENCE", "NOT", "NULL", "OR", "AS", "WITH", "INCREMENT",
    "BY", "START", "MAX", "IF", "EXISTS", "DROP",
}


def strip_comments_and_headers(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("--"):
            if "AUTO-FIX" in stripped or stripped.startswith("-- =="):
                continue
            if stripped.startswith("--"):
                continue
        lines.append(line)
    return "\n".join(lines)


def strip_index_preamble(text: str) -> str:
    """Remove IF EXISTS DROP INDEX batches from deployment index DDL."""
    parts = re.split(r"(?mi)^\s*GO\s*$", text)
    kept: list[str] = []
    for part in parts:
        if re.search(r"^\s*IF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+sys\.indexes", part, re.IGNORECASE | re.MULTILINE):
            if not re.search(r"CREATE\s+(?:UNIQUE\s+)?(?:NONCLUSTERED\s+)?INDEX", part, re.IGNORECASE):
                continue
        kept.append(part.strip())
    return "\n".join(p for p in kept if p)


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*\(\s*", " (", text)
    text = re.sub(r"\s*\)\s*", ") ", text)
    return text.strip()


def normalize_brackets(text: str) -> str:
    def _bracket(m: re.Match[str]) -> str:
        return f"[{m.group(1).upper()}]"

    return re.sub(r"\[([^\]]+)\]", _bracket, text, flags=re.IGNORECASE)


def normalize_fk_actions(text: str) -> str:
    text = re.sub(r"ON\s+DELETE\s+NO\s+ACTION", "ON DELETE NO ACTION", text, flags=re.IGNORECASE)
    text = re.sub(r"ON\s+UPDATE\s+NO\s+ACTION", "ON UPDATE NO ACTION", text, flags=re.IGNORECASE)
    text = re.sub(
        r"ON\s+DELETE\s+CASCADE\s+ON\s+UPDATE\s+NO\s+ACTION",
        "ON DELETE CASCADE ON UPDATE NO ACTION",
        text,
        flags=re.IGNORECASE,
    )
    return text


def normalize_table_columns(text: str) -> str:
    """Normalize table column defaults and datetime precision for comparison."""
    text = re.sub(
        r"DEFAULT\s*\(\s*sysdatetime\s*\(\s*\)\s*\)",
        "DEFAULT SYSDATETIME()",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"DEFAULT\s*\(\s*getdate\s*\(\s*\)\s*\)",
        "DEFAULT GETDATE()",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bDATETIME2(\s+NOT\s+NULL|\s+NULL|\s+DEFAULT)", r"DATETIME2(7)\1", text, flags=re.IGNORECASE)
    text = re.sub(
        r"IDENTITY\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)",
        r"IDENTITY(\1,\2)",
        text,
        flags=re.IGNORECASE,
    )
    return text


def uppercase_keywords(text: str) -> str:
    def _kw(m: re.Match[str]) -> str:
        word = m.group(0).upper()
        return word if word in _SQL_KEYWORDS else m.group(0)

    return re.sub(r"\b[A-Za-z_]+\b", _kw, text)


def normalize_ddl(text: str, object_type: str = "") -> str:
    if not text:
        return ""
    out = strip_comments_and_headers(text)
    if object_type == "INDEX":
        out = strip_index_preamble(out)
    if object_type == "TABLE":
        out = normalize_table_columns(out)
    out = normalize_fk_actions(out)
    out = normalize_brackets(out)
    out = normalize_whitespace(out)
    out = uppercase_keywords(out)
    return out.rstrip(" ;") + ";"


def ddl_equal(a: str, b: str, object_type: str = "") -> bool:
    return normalize_ddl(a, object_type) == normalize_ddl(b, object_type)


def normalize_pair(a: str, b: str, object_type: str = "") -> tuple[str, str, bool]:
    na = normalize_ddl(a, object_type)
    nb = normalize_ddl(b, object_type)
    return na, nb, na == nb
