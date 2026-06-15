"""Thin wrapper around ``ibm_db`` for read-only catalog queries.

Each database is queried independently; connection or query failures are
captured per database (never raised to the caller) so that one unreachable
host does not abort a multi-database run.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from connections_loader import Connection
from queries import BuiltQuery, build_query

try:  # ibm_db is an optional import so the module can be inspected without it.
    import ibm_db  # type: ignore
except Exception:  # pragma: no cover - exercised only when driver missing.
    ibm_db = None


@dataclass
class DBResult:
    """Outcome of querying a single database."""

    connection: Connection
    rows: list[dict] = field(default_factory=list)
    status: str = "ok"
    error: str = ""
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def match_count(self) -> int:
        return len(self.rows)


def _conn_string(conn: Connection, user: str, password: str) -> str:
    return (
        f"DATABASE={conn.dbname};"
        f"HOSTNAME={conn.host};"
        f"PORT={conn.port};"
        f"PROTOCOL=TCPIP;"
        f"UID={user};"
        f"PWD={password};"
    )


@dataclass
class QueryOutcome:
    """Result of a single read-only SQL execution on one DB2 database."""

    rows: list[dict] = field(default_factory=list)
    status: str = "ok"
    error: str = ""
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def query_single(
    conn: Connection,
    user: str,
    password: str,
    sql: str,
    params: tuple | list = (),
) -> QueryOutcome:
    """Connect, run arbitrary read-only SQL, return rows as dicts (uppercase keys)."""
    start = time.perf_counter()
    if ibm_db is None:
        return QueryOutcome(
            status="error",
            error="ibm_db driver is not installed (pip install ibm_db).",
        )

    handle = None
    try:
        handle = ibm_db.connect(_conn_string(conn, user, password), "", "")
    except Exception as exc:
        return QueryOutcome(
            status="unreachable",
            error=str(exc).strip(),
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )

    try:
        stmt = ibm_db.prepare(handle, sql)
        ibm_db.execute(stmt, tuple(params))
        rows: list[dict] = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            rows.append({str(k).upper(): v for k, v in row.items()})
            row = ibm_db.fetch_assoc(stmt)
        return QueryOutcome(
            rows=rows,
            status="ok",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    except Exception as exc:
        return QueryOutcome(
            status="error",
            error=str(exc).strip(),
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    finally:
        try:
            ibm_db.close(handle)
        except Exception:
            pass


def query_database(
    conn: Connection,
    user: str,
    password: str,
    built: BuiltQuery,
) -> DBResult:
    """Connect to one database, run the prepared query, return normalized rows."""
    start = time.perf_counter()
    if ibm_db is None:
        return DBResult(
            connection=conn,
            status="error",
            error="ibm_db driver is not installed (pip install ibm_db).",
        )

    handle = None
    try:
        handle = ibm_db.connect(_conn_string(conn, user, password), "", "")
    except Exception as exc:  # connection failures (auth, host down, etc.)
        return DBResult(
            connection=conn,
            status="unreachable",
            error=str(exc).strip(),
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )

    try:
        stmt = ibm_db.prepare(handle, built.sql)
        ibm_db.execute(stmt, tuple(built.params))
        rows: list[dict] = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            rows.append(
                {
                    "Schema": row.get("SCHEMA"),
                    "Object Name": row.get("OBJECT_NAME"),
                    "Object Type": row.get("OBJECT_TYPE"),
                    "Sub Type": row.get("SUB_TYPE"),
                    "Create Time": row.get("CREATE_TIME"),
                }
            )
            row = ibm_db.fetch_assoc(stmt)
        return DBResult(
            connection=conn,
            rows=rows,
            status="ok",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    except Exception as exc:  # query/catalog errors
        return DBResult(
            connection=conn,
            status="error",
            error=str(exc).strip(),
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    finally:
        try:
            ibm_db.close(handle)
        except Exception:
            pass


def run_across_databases(
    connections: list[Connection],
    user: str,
    password: str,
    object_type: str,
    operator: str,
    text: str,
    *,
    include_system: bool = False,
    max_workers: int = 8,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[DBResult]:
    """Run the same object search against every database concurrently.

    ``on_progress(done, total)`` is invoked after each database completes so a
    UI can render a progress bar.
    """
    built = build_query(object_type, operator, text, include_system=include_system)
    total = len(connections)
    results: list[DBResult] = []
    done = 0

    workers = max(1, min(max_workers, total)) if total else 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(query_database, conn, user, password, built): conn
            for conn in connections
        }
        for future in as_completed(futures):
            results.append(future.result())
            done += 1
            if on_progress:
                on_progress(done, total)

    # Stable ordering by dbname/host for predictable display.
    results.sort(key=lambda r: (r.connection.dbname.upper(), r.connection.host.lower()))
    return results
