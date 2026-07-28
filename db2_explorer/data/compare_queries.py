"""SQL templates for DB2 vs Azure SQL table row-count comparison."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompareQuery:
    sql: str
    params: tuple[str, ...]


# ---------------------------------------------------------------------------
# UNION query generators (user-provided patterns, schema as bound param)
# ---------------------------------------------------------------------------

DB2_UNION_GENERATOR = CompareQuery(
    sql="""
SELECT
  LISTAGG(
    CAST(
      'SELECT ''' || STRIP(TABSCHEMA) || ''' AS SCHEMANAME, '''
      || STRIP(TABNAME) || ''' AS TABLENAME, COUNT(*) AS EXACTCOUNT FROM '
      || STRIP(TABSCHEMA) || '.' || STRIP(TABNAME) AS VARCHAR(32000)
    ),
    ' UNION ALL '
  ) WITHIN GROUP (ORDER BY TABSCHEMA, TABNAME)
  || ' ORDER BY TABLENAME ASC' AS UNION_QUERY
FROM SYSCAT.TABLES
WHERE TYPE = 'T' AND TABSCHEMA = ?
""".strip(),
    params=(),
)

AZURE_UNION_GENERATOR = CompareQuery(
    sql="""
SELECT
    STRING_AGG(
        CAST(
            'SELECT ''' + s.name + ''' AS SCHEMANAME, ''' + t.name
            + ''' AS TABLENAME, COUNT(*) AS EXACTCOUNT FROM '
            + QUOTENAME(s.name) + '.' + QUOTENAME(t.name) AS NVARCHAR(MAX)
        ),
        ' UNION ALL '
    ) WITHIN GROUP (ORDER BY s.name, t.name)
    + ' ORDER BY TABLENAME ASC' AS UNION_QUERY
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE s.name = ?
""".strip(),
    params=(),
)

# ---------------------------------------------------------------------------
# Fallback: simple table lists when UNION generation/execution fails
# ---------------------------------------------------------------------------

DB2_TABLE_LIST = CompareQuery(
    sql="""
SELECT STRIP(TABSCHEMA) AS SCHEMANAME, STRIP(TABNAME) AS TABLENAME
FROM SYSCAT.TABLES
WHERE TYPE = 'T' AND TABSCHEMA = ?
ORDER BY TABNAME
""".strip(),
    params=(),
)

AZURE_TABLE_LIST = CompareQuery(
    sql="""
SELECT s.name AS SCHEMANAME, t.name AS TABLENAME
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE s.name = ?
ORDER BY t.name
""".strip(),
    params=(),
)


def db2_count_sql(schema: str, table: str) -> str:
    """Single-table COUNT for DB2 fallback path."""
    schema = schema.strip()
    table = table.strip()
    return f"SELECT '{schema}' AS SCHEMANAME, '{table}' AS TABLENAME, COUNT(*) AS EXACTCOUNT FROM {schema}.{table}"


def azure_count_sql(schema: str, table: str) -> str:
    """Single-table COUNT for Azure fallback path."""
    schema = schema.strip().replace("]", "]]")
    table = table.strip().replace("]", "]]")
    return (
        f"SELECT '{schema}' AS SCHEMANAME, '{table}' AS TABLENAME, "
        f"COUNT(*) AS EXACTCOUNT FROM [{schema}].[{table}]"
    )


def with_schema(query: CompareQuery, schema: str) -> CompareQuery:
    """Bind a schema name to a template that has one ``?`` placeholder."""
    return CompareQuery(sql=query.sql, params=(schema,))
