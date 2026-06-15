"""Orchestrate DB2 vs Azure table row-count comparison."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from azure_client import AzureConnection, AzureQueryOutcome, query as azure_query
from compare_queries import (
    AZURE_TABLE_LIST,
    AZURE_UNION_GENERATOR,
    DB2_TABLE_LIST,
    DB2_UNION_GENERATOR,
    azure_count_sql,
    db2_count_sql,
    with_schema,
)
from connections_loader import Connection
from db2_client import QueryOutcome, query_single

# DB2 LISTAGG VARCHAR(32000) — treat near-limit output as risky.
_DB2_UNION_MAX_LEN = 30000
_FALLBACK_BATCH = 8


@dataclass
class TableCount:
    table_name: str
    schema: str
    exact_count: int


@dataclass
class SideResult:
    counts: list[TableCount] = field(default_factory=list)
    union_sql: str = ""
    used_fallback: bool = False
    status: str = "ok"
    error: str = ""


@dataclass
class CompareResult:
    comparison: pd.DataFrame = field(default_factory=pd.DataFrame)
    db2: SideResult = field(default_factory=SideResult)
    azure: SideResult = field(default_factory=SideResult)
    status: str = "ok"
    error: str = ""


def _normalize_table_name(name: str) -> str:
    return (name or "").strip().upper()


def _parse_count_rows(rows: list[dict]) -> list[TableCount]:
    counts: list[TableCount] = []
    for row in rows:
        schema = str(row.get("SCHEMANAME") or row.get("SCHEMA") or "").strip()
        table = str(row.get("TABLENAME") or row.get("TABLE_NAME") or "").strip()
        raw = row.get("EXACTCOUNT")
        if not table:
            continue
        try:
            exact = int(raw) if raw is not None else 0
        except (TypeError, ValueError):
            exact = 0
        counts.append(TableCount(table_name=table, schema=schema, exact_count=exact))
    return counts


def _union_needs_fallback(outcome: QueryOutcome | AzureQueryOutcome, union_sql: str) -> bool:
    if not outcome.ok:
        return True
    if not union_sql or not union_sql.strip():
        return True
    if len(union_sql) >= _DB2_UNION_MAX_LEN:
        return True
    return False


def _fetch_db2_table_list(
    conn: Connection, user: str, password: str, schema: str
) -> QueryOutcome:
    q = with_schema(DB2_TABLE_LIST, schema)
    return query_single(conn, user, password, q.sql, q.params)


def _fetch_azure_table_list(conn: AzureConnection, schema: str) -> AzureQueryOutcome:
    q = with_schema(AZURE_TABLE_LIST, schema)
    return azure_query(conn, q.sql, q.params)


def _db2_fallback_counts(
    conn: Connection,
    user: str,
    password: str,
    schema: str,
    tables: list[tuple[str, str]],
) -> QueryOutcome:
    if not tables:
        return QueryOutcome(rows=[], status="ok")

    all_rows: list[dict] = []

    def _one(tbl: tuple[str, str]) -> list[dict]:
        sch, name = tbl
        sql = db2_count_sql(sch, name)
        result = query_single(conn, user, password, sql)
        return result.rows if result.ok else []

    workers = min(_FALLBACK_BATCH, len(tables))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, t) for t in tables]
        for fut in as_completed(futures):
            all_rows.extend(fut.result())

    if not all_rows:
        return QueryOutcome(status="error", error="Fallback per-table counts returned no rows.")
    return QueryOutcome(rows=all_rows, status="ok")


def _azure_fallback_counts(
    conn: AzureConnection,
    schema: str,
    tables: list[tuple[str, str]],
) -> AzureQueryOutcome:
    if not tables:
        return AzureQueryOutcome(rows=[], status="ok")

    all_rows: list[dict] = []

    def _one(tbl: tuple[str, str]) -> list[dict]:
        sch, name = tbl
        sql = azure_count_sql(sch, name)
        result = azure_query(conn, sql)
        return result.rows if result.ok else []

    workers = min(_FALLBACK_BATCH, len(tables))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, t) for t in tables]
        for fut in as_completed(futures):
            all_rows.extend(fut.result())

    if not all_rows:
        return AzureQueryOutcome(status="error", error="Fallback per-table counts returned no rows.")
    return AzureQueryOutcome(rows=all_rows, status="ok")


def _run_db2_side(
    conn: Connection,
    user: str,
    password: str,
    schema: str,
) -> SideResult:
    side = SideResult()
    gen = with_schema(DB2_UNION_GENERATOR, schema)
    gen_out = query_single(conn, user, password, gen.sql, gen.params)
    if not gen_out.ok:
        side.status = gen_out.status
        side.error = gen_out.error
        return side

    union_sql = ""
    if gen_out.rows:
        union_sql = str(gen_out.rows[0].get("UNION_QUERY") or "").strip()
    side.union_sql = union_sql

    if _union_needs_fallback(gen_out, union_sql):
        side.used_fallback = True
        list_out = _fetch_db2_table_list(conn, user, password, schema)
        if not list_out.ok:
            side.status = list_out.status
            side.error = list_out.error or "Could not list DB2 tables for fallback."
            return side
        tables = [
            (str(r.get("SCHEMANAME", schema)), str(r.get("TABLENAME", "")))
            for r in list_out.rows
            if r.get("TABLENAME")
        ]
        count_out = _db2_fallback_counts(conn, user, password, schema, tables)
        if not count_out.ok:
            side.status = count_out.status
            side.error = count_out.error
            return side
        side.counts = _parse_count_rows(count_out.rows)
        return side

    count_out = query_single(conn, user, password, union_sql)
    if not count_out.ok:
        side.used_fallback = True
        list_out = _fetch_db2_table_list(conn, user, password, schema)
        if not list_out.ok:
            side.status = count_out.status
            side.error = count_out.error
            return side
        tables = [
            (str(r.get("SCHEMANAME", schema)), str(r.get("TABLENAME", "")))
            for r in list_out.rows
            if r.get("TABLENAME")
        ]
        count_out = _db2_fallback_counts(conn, user, password, schema, tables)
        if not count_out.ok:
            side.status = count_out.status
            side.error = count_out.error
            return side

    side.counts = _parse_count_rows(count_out.rows)
    return side


def _run_azure_side(conn: AzureConnection, schema: str) -> SideResult:
    side = SideResult()
    gen = with_schema(AZURE_UNION_GENERATOR, schema)
    gen_out = azure_query(conn, gen.sql, gen.params)
    if not gen_out.ok:
        side.status = gen_out.status
        side.error = gen_out.error
        return side

    union_sql = ""
    if gen_out.rows:
        union_sql = str(gen_out.rows[0].get("UNION_QUERY") or "").strip()
    side.union_sql = union_sql

    if _union_needs_fallback(gen_out, union_sql):
        side.used_fallback = True
        list_out = _fetch_azure_table_list(conn, schema)
        if not list_out.ok:
            side.status = list_out.status
            side.error = list_out.error or "Could not list Azure tables for fallback."
            return side
        tables = [
            (str(r.get("SCHEMANAME", schema)), str(r.get("TABLENAME", "")))
            for r in list_out.rows
            if r.get("TABLENAME")
        ]
        count_out = _azure_fallback_counts(conn, schema, tables)
        if not count_out.ok:
            side.status = count_out.status
            side.error = count_out.error
            return side
        side.counts = _parse_count_rows(count_out.rows)
        return side

    count_out = azure_query(conn, union_sql)
    if not count_out.ok:
        side.used_fallback = True
        list_out = _fetch_azure_table_list(conn, schema)
        if not list_out.ok:
            side.status = count_out.status
            side.error = count_out.error
            return side
        tables = [
            (str(r.get("SCHEMANAME", schema)), str(r.get("TABLENAME", "")))
            for r in list_out.rows
            if r.get("TABLENAME")
        ]
        count_out = _azure_fallback_counts(conn, schema, tables)
        if not count_out.ok:
            side.status = count_out.status
            side.error = count_out.error
            return side

    side.counts = _parse_count_rows(count_out.rows)
    return side


def _merge_counts(
    db2_counts: list[TableCount],
    azure_counts: list[TableCount],
    db2_schema: str,
    azure_schema: str,
) -> pd.DataFrame:
    db2_map = {_normalize_table_name(c.table_name): c for c in db2_counts}
    azure_map = {_normalize_table_name(c.table_name): c for c in azure_counts}
    all_tables = sorted(set(db2_map) | set(azure_map))

    records: list[dict] = []
    for key in all_tables:
        d = db2_map.get(key)
        a = azure_map.get(key)
        db2_count = d.exact_count if d else None
        azure_count = a.exact_count if a else None

        if d and a:
            if db2_count == azure_count:
                status = "Match"
            else:
                status = "Mismatch"
        elif d:
            status = "DB2 only"
        else:
            status = "Azure only"

        delta = None
        if db2_count is not None and azure_count is not None:
            delta = azure_count - db2_count

        records.append(
            {
                "Table Name": (d or a).table_name if (d or a) else key,
                "DB2 Schema": db2_schema if d else "",
                "Azure Schema": azure_schema if a else "",
                "DB2 Count": db2_count,
                "Azure Count": azure_count,
                "Delta": delta,
                "Status": status,
            }
        )

    return pd.DataFrame.from_records(records)


def _summary_metrics(df: pd.DataFrame) -> dict[str, int]:
    if df.empty:
        return {
            "tables_db2": 0,
            "tables_azure": 0,
            "matched": 0,
            "mismatched": 0,
            "missing": 0,
        }
    return {
        "tables_db2": int(df["DB2 Count"].notna().sum()),
        "tables_azure": int(df["Azure Count"].notna().sum()),
        "matched": int((df["Status"] == "Match").sum()),
        "mismatched": int((df["Status"] == "Mismatch").sum()),
        "missing": int(df["Status"].isin(["DB2 only", "Azure only"]).sum()),
    }


def run_comparison(
    db2_conn: Connection,
    db2_user: str,
    db2_password: str,
    db2_schema: str,
    azure_conn: AzureConnection,
    azure_schema: str,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> CompareResult:
    """Run full comparison pipeline and return merged results."""
    result = CompareResult()
    total = 3
    step = 0

    def _progress(msg: str) -> None:
        nonlocal step
        step += 1
        if on_progress:
            on_progress(step, total, msg)

    _progress("Execute DB2 counts")
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_db2 = pool.submit(_run_db2_side, db2_conn, db2_user, db2_password, db2_schema)
        f_az = pool.submit(_run_azure_side, azure_conn, azure_schema)
        result.db2 = f_db2.result()
        result.azure = f_az.result()

    _progress("Execute Azure counts")

    if result.db2.status != "ok":
        result.status = result.db2.status
        result.error = f"DB2: {result.db2.error}"
        return result
    if result.azure.status != "ok":
        result.status = result.azure.status
        result.error = f"Azure: {result.azure.error}"
        return result

    _progress("Build comparison")
    result.comparison = _merge_counts(
        result.db2.counts,
        result.azure.counts,
        db2_schema,
        azure_schema,
    )
    result.status = "ok"
    return result


def filter_comparison(df: pd.DataFrame, view: str) -> pd.DataFrame:
    if df.empty:
        return df
    if view == "Mismatches only":
        return df[df["Status"] == "Mismatch"].copy()
    if view == "DB2 only":
        return df[df["Status"] == "DB2 only"].copy()
    if view == "Azure only":
        return df[df["Status"] == "Azure only"].copy()
    return df.copy()


def comparison_metrics(df: pd.DataFrame) -> dict[str, int]:
    return _summary_metrics(df)
