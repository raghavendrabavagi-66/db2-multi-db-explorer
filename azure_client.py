"""Azure SQL / SQL Server target client using pyodbc."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

try:
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover
    pyodbc = None

ODBC_DRIVER = "ODBC Driver 18 for SQL Server"

AzureAuthMethod = Literal["azure_ad_interactive", "windows_integrated"]

AUTH_METHOD_LABELS = {
    "azure_ad_interactive": "Azure AD — email + browser sign-in (MFA)",
    "windows_integrated": "Windows integrated (SSMS-style, current Windows login)",
}


@dataclass(frozen=True)
class AzureConnection:
    server: str
    database: str
    email: str = ""
    auth_method: AzureAuthMethod = "azure_ad_interactive"
    trust_server_certificate: bool = False


@dataclass
class AzureQueryOutcome:
    rows: list[dict] = field(default_factory=list)
    status: str = "ok"
    error: str = ""
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _host_only(server: str) -> str:
    """Strip instance or port suffix for cloud-host detection."""
    s = server.strip()
    if s.lower().startswith("tcp:"):
        s = s[4:]
    if "\\" in s:
        return s.split("\\", 1)[0]
    if "," in s:
        return s.split(",", 1)[0]
    return s


def _is_azure_sql_host(server: str) -> bool:
    host = _host_only(server).lower()
    return ".database.windows.net" in host or ".database.usgovcloudapi.net" in host


def _server_value(server: str) -> str:
    """Format Server= for ODBC (SSMS-compatible).

    - Named instance ``host\\instance`` — no forced port 1433 (SSMS default).
    - ``host,port`` or ``tcp:host,port`` — unchanged apart from optional tcp prefix.
    - Plain hostname (e.g. Azure SQL) — ``tcp:host,1433``.
    """
    server = server.strip()
    if not server:
        return server
    if server.lower().startswith("tcp:"):
        return server
    if "\\" in server:
        return server
    if "," in server:
        return f"tcp:{server}"
    return f"tcp:{server},1433"


def _connection_string(conn: AzureConnection) -> str:
    """Build ODBC connection string for the selected authentication mode."""
    trust = "yes" if conn.trust_server_certificate else "no"
    parts = [
        f"Driver={{{ODBC_DRIVER}}}",
        f"Server={_server_value(conn.server)}",
        f"Database={conn.database.strip()}",
        "Encrypt=yes",
        f"TrustServerCertificate={trust}",
    ]
    if conn.auth_method == "windows_integrated":
        if _is_azure_sql_host(conn.server):
            parts.append("Authentication=ActiveDirectoryIntegrated")
        else:
            # On-prem / named instance — same as SSMS Windows authentication
            parts.append("Trusted_Connection=yes")
    else:
        parts.append("Authentication=ActiveDirectoryInteractive")
        parts.append(f"UID={conn.email.strip()}")
    return ";".join(parts) + ";"


def test_connection(conn: AzureConnection) -> AzureQueryOutcome:
    """Validate target connectivity with a lightweight query."""
    return query(conn, "SELECT 1 AS OK", ())


def query(
    conn: AzureConnection,
    sql: str,
    params: tuple | list = (),
) -> AzureQueryOutcome:
    """Run read-only SQL against the target SQL Server / Azure SQL."""
    start = time.perf_counter()
    if pyodbc is None:
        return AzureQueryOutcome(
            status="error",
            error="pyodbc is not installed (pip install pyodbc).",
        )

    if conn.auth_method == "azure_ad_interactive" and not conn.email.strip():
        return AzureQueryOutcome(
            status="error",
            error="Email (UPN) is required for Azure AD sign-in.",
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
