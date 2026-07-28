"""Parse and merge DB2 connection lists from one or more CSV files.

Accepted formats (header optional, separators tolerant):
    dbname,host,port
    dbname,host
    DBname host           (whitespace separated)

A default port is applied when none is given.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Iterable

DEFAULT_PORT = 50000

# Default path for the persisted in-app working list.
CONNECTIONS_FILE = "connections.csv"

# Tokens that, when seen as the first row, indicate a header line to skip.
_HEADER_TOKENS = {"dbname", "db", "database", "databasename", "db_name"}


@dataclass(frozen=True)
class Connection:
    """A single DB2 LUW connection target."""

    dbname: str
    host: str
    port: int = DEFAULT_PORT

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.dbname.upper(), self.host.lower(), self.port)


def _split_row(raw: str) -> list[str]:
    """Split a single line on commas, tabs, semicolons or whitespace."""
    raw = raw.strip()
    if not raw:
        return []
    # Prefer explicit delimiters; fall back to any run of whitespace.
    if "," in raw or "\t" in raw or ";" in raw:
        parts = re.split(r"[,\t;]+", raw)
    else:
        parts = re.split(r"\s+", raw)
    return [p.strip() for p in parts if p.strip()]


def _looks_like_header(parts: list[str]) -> bool:
    return bool(parts) and parts[0].lower() in _HEADER_TOKENS


def parse_text(text: str) -> list[Connection]:
    """Parse the raw text of a single CSV/list file into connections."""
    conns: list[Connection] = []
    for lineno, line in enumerate(io.StringIO(text)):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = _split_row(stripped)
        if not parts:
            continue
        if lineno == 0 and _looks_like_header(parts):
            continue
        if len(parts) < 2:
            # Not enough info to form a connection; skip silently.
            continue
        dbname, host = parts[0], parts[1]
        port = DEFAULT_PORT
        if len(parts) >= 3:
            try:
                port = int(parts[2])
            except ValueError:
                port = DEFAULT_PORT
        conns.append(Connection(dbname=dbname, host=host, port=port))
    return conns


def load_files(sources: Iterable[tuple[str, str]]) -> list[Connection]:
    """Parse and merge multiple sources.

    ``sources`` is an iterable of ``(label, text)`` pairs (label is unused for
    parsing but keeps call sites readable). Duplicate connections are removed
    while preserving first-seen order.
    """
    seen: set[tuple[str, str, int]] = set()
    merged: list[Connection] = []
    for _label, text in sources:
        for conn in parse_text(text):
            if conn.key in seen:
                continue
            seen.add(conn.key)
            merged.append(conn)
    return merged


def load_paths(paths: Iterable[str]) -> list[Connection]:
    """Convenience helper to load connections directly from file paths."""
    sources: list[tuple[str, str]] = []
    for path in paths:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            sources.append((path, fh.read()))
    return load_files(sources)


def _coerce_port(value: object) -> int:
    """Best-effort conversion of a port value to int, falling back to default."""
    if value is None:
        return DEFAULT_PORT
    try:
        # Handles ints, floats (e.g. from pandas) and numeric strings.
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return DEFAULT_PORT


def connections_from_rows(rows: Iterable[object]) -> list[Connection]:
    """Build connections from tabular rows (e.g. an edited data grid).

    Each row may be a mapping with ``dbname``/``host``/``port`` keys (case
    flexible, also accepts ``database``) or a positional sequence
    ``(dbname, host[, port])``. Rows missing a dbname or host are skipped,
    ports are coerced to int (default applied on failure), and duplicates are
    removed while preserving first-seen order.
    """
    seen: set[tuple[str, str, int]] = set()
    result: list[Connection] = []
    for row in rows:
        dbname = host = ""
        port: object = DEFAULT_PORT

        if isinstance(row, dict):
            lowered = {str(k).strip().lower(): v for k, v in row.items()}
            dbname = str(lowered.get("dbname") or lowered.get("database") or "").strip()
            host = str(lowered.get("host") or "").strip()
            port = lowered.get("port", DEFAULT_PORT)
        else:
            seq = list(row)
            if len(seq) >= 1 and seq[0] is not None:
                dbname = str(seq[0]).strip()
            if len(seq) >= 2 and seq[1] is not None:
                host = str(seq[1]).strip()
            if len(seq) >= 3:
                port = seq[2]

        if not dbname or not host:
            continue

        conn = Connection(dbname=dbname, host=host, port=_coerce_port(port))
        if conn.key in seen:
            continue
        seen.add(conn.key)
        result.append(conn)
    return result


def save_connections(path: str, connections: Iterable[Connection]) -> None:
    """Write connections to ``path`` as a ``dbname,host,port`` CSV with header."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["dbname", "host", "port"])
        for conn in connections:
            writer.writerow([conn.dbname, conn.host, conn.port])


# DBeaver-style: jdbc:db2://host:port/database  (also accepts db2:// without jdbc:)
_JDBC_DB2_RE = re.compile(
    r"^(?:jdbc:)?db2://([^:/\s]+)(?::(\d+))?/([^?;\s/]+)",
    re.IGNORECASE,
)


def parse_jdbc_db2_url(url: str) -> tuple[str, str, int] | None:
    """Parse ``jdbc:db2://host:port/dbname`` into ``(dbname, host, port)``.

    Matches DBeaver's default URL shape, e.g. ``jdbc:db2://ss-db22d:50000/infoq``
    → ``(infoq, ss-db22d, 50000)``. Port defaults to 50000 when omitted.
    """
    text = (url or "").strip()
    if not text:
        return None
    match = _JDBC_DB2_RE.match(text)
    if not match:
        return None
    host, port_str, dbname = match.group(1), match.group(2), match.group(3)
    return (dbname.strip(), host.strip(), _coerce_port(port_str))


def _split_paste_line(line: str) -> list[str]:
    """Split one pasted line into cells (tab, comma, or semicolon)."""
    line = line.strip()
    if not line:
        return []
    if "\t" in line:
        parts = line.split("\t")
    elif ";" in line and "," not in line:
        parts = line.split(";")
    elif "," in line:
        parts = line.split(",")
    else:
        parts = re.split(r"\s+", line)
    return [p.strip().strip('"').strip("'") for p in parts if p.strip()]


def parse_pasted_table(text: str) -> list[tuple[str, str, int]]:
    """Parse clipboard text copied from Excel or a CSV into connection rows.

    Excel copies columns as tab-separated and rows as newlines. Commas and
    whitespace-separated lines are also accepted. An optional header row
    (``dbname``, ``database``, ``host``, …) is skipped automatically.

    Returns ``(dbname, host, port)`` tuples; rows without dbname and host are
    omitted.
    """
    if not text or not text.strip():
        return []

    lines = [ln for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip()]
    if not lines:
        return []

    rows: list[tuple[str, str, int]] = []
    tabular_lines: list[str] = []

    for line in lines:
        jdbc_row = parse_jdbc_db2_url(line)
        if jdbc_row:
            rows.append(jdbc_row)
        else:
            tabular_lines.append(line)

    if tabular_lines:
        parsed: list[list[str]] = [_split_paste_line(ln) for ln in tabular_lines]
        parsed = [p for p in parsed if p]

        if parsed and _looks_like_header(parsed[0]):
            parsed = parsed[1:]

        for parts in parsed:
            if len(parts) < 2:
                continue
            dbname, host = parts[0], parts[1]
            port = _coerce_port(parts[2]) if len(parts) >= 3 else DEFAULT_PORT
            if dbname and host:
                rows.append((dbname, host, port))

    return rows
