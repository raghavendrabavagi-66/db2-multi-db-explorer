"""Azure SQL client using pyodbc with Azure AD Interactive (MFA) authentication."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

try:
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover
    pyodbc = None

ODBC_DRIVER = "ODBC Driver 18 for SQL Server"


@dataclass(frozen=True)
class AzureConnection:
    server: str
    database: str
    email: str


@dataclass
class AzureQueryOutcome:
    rows: list[dict] = field(default_factory=list)
    status: str = "ok"
    error: str = ""
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _connection_string(conn: AzureConnection) -> str:
    server = conn.server.strip()
    if not server.lower().startswith("tcp:"):
        server = f"tcp:{server},1433"
    return (
        f"Driver={{{ODBC_DRIVER}}};"
        f"Server={server};"
        f"Database={conn.database};"
        f"Authentication=ActiveDirectoryInteractive;"
        f"UID={conn.email};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
    )


def test_connection(conn: AzureConnection) -> AzureQueryOutcome:
    """Validate Azure connectivity with a lightweight query."""
    return query(conn, "SELECT 1 AS OK", ())


def query(
    conn: AzureConnection,
    sql: str,
    params: tuple | list = (),
) -> AzureQueryOutcome:
    """Run read-only SQL against Azure SQL; may open browser for MFA."""
    start = time.perf_counter()
    if pyodbc is None:
        return AzureQueryOutcome(
            status="error",
            error="pyodbc is not installed (pip install pyodbc).",
        )

    handle = None
    try:
        handle = pyodbc.connect(_connection_string(conn), timeout=120)
    except Exception as exc:
        return AzureQueryOutcome(
            status="unreachable",
            error=str(exc).strip(),
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )

    try:
        cursor = handle.cursor()
        cursor.execute(sql, params)
        columns = [col[0].upper() for col in cursor.description] if cursor.description else []
        rows: list[dict] = []
        for record in cursor.fetchall():
            rows.append(dict(zip(columns, record)))
        return AzureQueryOutcome(
            rows=rows,
            status="ok",
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    except Exception as exc:
        return AzureQueryOutcome(
            status="error",
            error=str(exc).strip(),
            elapsed_ms=int((time.perf_counter() - start) * 1000),
        )
    finally:
        try:
            if handle is not None:
                handle.close()
        except Exception:
            pass
