"""Fetch live SQL Server / Azure SQL object definitions from catalog views."""

from __future__ import annotations

import re

from azure_client import AzureConnection, AzureQueryOutcome, query
from deployment_parser import make_object_key


def _bracket(name: str) -> str:
    return f"[{name.replace(']', ']]')}]"


def _qident(schema: str, name: str) -> str:
    return f"{_bracket(schema)}.{_bracket(name)}"


def _fetch(conn: AzureConnection, sql: str) -> AzureQueryOutcome:
    return query(conn, sql)


def _rows(out: AzureQueryOutcome) -> list[dict]:
    return out.rows if out.ok else []


def fetch_schemas(conn: AzureConnection) -> dict[str, str]:
    sql = """
SELECT name AS SCHEMA_NAME
FROM sys.schemas
WHERE name NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest')
  AND principal_id IS NOT NULL
ORDER BY name
"""
    result: dict[str, str] = {}
    for row in _rows(_fetch(conn, sql)):
        name = str(row.get("SCHEMA_NAME", "")).strip()
        if not name:
            continue
        ddl = f"CREATE SCHEMA {_bracket(name)}"
        key = make_object_key("SCHEMA", "", name)
        result[key] = ddl
    return result


def fetch_roles(conn: AzureConnection) -> dict[str, str]:
    sql = """
SELECT name AS ROLE_NAME
FROM sys.database_principals
WHERE type = 'R' AND is_fixed_role = 0 AND name NOT IN ('public')
ORDER BY name
"""
    result: dict[str, str] = {}
    for row in _rows(_fetch(conn, sql)):
        name = str(row.get("ROLE_NAME", "")).strip()
        if not name:
            continue
        key = make_object_key("ROLE", "", name)
        result[key] = f"CREATE ROLE {_bracket(name)}"
    return result


def _column_type_sql(type_name: str, max_len, prec, scale) -> str:
    type_name = type_name.lower()
    if type_name in ("varchar", "char", "varbinary", "binary"):
        if type_name in ("varchar", "varbinary") and max_len == -1:
            return f"{type_name.upper()}(MAX)"
        length = int(max_len) if max_len else 0
        return f"{type_name.upper()}({length})"
    if type_name in ("nvarchar", "nchar"):
        if max_len == -1:
            return f"{type_name.upper()}(MAX)"
        length = int(max_len) // 2 if max_len else 0
        return f"{type_name.upper()}({length})"
    if type_name in ("decimal", "numeric"):
        return f"{type_name.upper()}({prec},{scale})"
    if type_name in ("datetime2", "datetimeoffset", "time"):
        return f"{type_name.upper()}({int(scale or 7)})"
    return type_name.upper()


def _format_column_default(definition: str) -> str:
    """Format sys.default_constraints.definition for CREATE TABLE column DDL."""
    d = (definition or "").strip()
    if not d:
        return ""
    if d.startswith("(") and d.endswith(")"):
        d = d[1:-1].strip()
    if re.match(r"sysdatetime\s*\(\s*\)\s*$", d, re.IGNORECASE):
        return " DEFAULT SYSDATETIME()"
    if re.match(r"getdate\s*\(\s*\)\s*$", d, re.IGNORECASE):
        return " DEFAULT GETDATE()"
    if re.match(r"getutcdate\s*\(\s*\)\s*$", d, re.IGNORECASE):
        return " DEFAULT GETUTCDATE()"
    return f" DEFAULT {d.upper()}"


def _format_identity(seed, increment) -> str:
    if seed is None and increment is None:
        return ""
    try:
        seed_i = int(seed)
    except (TypeError, ValueError):
        seed_i = 1
    try:
        inc_i = int(increment)
    except (TypeError, ValueError):
        inc_i = 1
    return f" IDENTITY({seed_i},{inc_i})"


def _fetch_column_defaults(conn: AzureConnection) -> dict[tuple[str, str, str], str]:
    sql = """
SELECT
    s.name AS SCHEMA_NAME,
    t.name AS TABLE_NAME,
    c.name AS COLUMN_NAME,
    dc.definition AS DEFAULT_DEFINITION
FROM sys.default_constraints dc
JOIN sys.columns c
    ON dc.parent_object_id = c.object_id
   AND dc.parent_column_id = c.column_id
JOIN sys.tables t ON c.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE t.is_ms_shipped = 0
"""
    defaults: dict[tuple[str, str, str], str] = {}
    for row in _rows(_fetch(conn, sql)):
        schema = str(row.get("SCHEMA_NAME", ""))
        table = str(row.get("TABLE_NAME", ""))
        col = str(row.get("COLUMN_NAME", ""))
        defn = str(row.get("DEFAULT_DEFINITION", "") or "").strip()
        if defn:
            defaults[(schema, table, col)] = defn
    return defaults


def fetch_tables(conn: AzureConnection) -> dict[str, str]:
    defaults = _fetch_column_defaults(conn)
    sql = """
SELECT
    s.name AS SCHEMA_NAME,
    t.name AS TABLE_NAME,
    c.name AS COLUMN_NAME,
    ty.name AS TYPE_NAME,
    c.max_length,
    c.precision,
    c.scale,
    c.is_nullable,
    c.column_id,
    CAST(ic.seed_value AS BIGINT) AS IDENTITY_SEED,
    CAST(ic.increment_value AS BIGINT) AS IDENTITY_INCREMENT
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.columns c ON c.object_id = t.object_id
JOIN sys.types ty ON c.user_type_id = ty.user_type_id
LEFT JOIN sys.identity_columns ic
    ON ic.object_id = c.object_id
   AND ic.column_id = c.column_id
WHERE t.is_ms_shipped = 0
ORDER BY s.name, t.name, c.column_id
"""
    grouped: dict[tuple[str, str], list[str]] = {}
    for row in _rows(_fetch(conn, sql)):
        schema = str(row.get("SCHEMA_NAME", ""))
        table = str(row.get("TABLE_NAME", ""))
        col = str(row.get("COLUMN_NAME", ""))
        type_name = str(row.get("TYPE_NAME", "")).lower()
        max_len = row.get("MAX_LENGTH")
        prec = row.get("PRECISION")
        scale = row.get("SCALE")
        nullable = row.get("IS_NULLABLE")

        type_sql = _column_type_sql(type_name, max_len, prec, scale)
        identity_sql = _format_identity(row.get("IDENTITY_SEED"), row.get("IDENTITY_INCREMENT"))
        null_sql = " NULL" if nullable else " NOT NULL"
        default_sql = _format_column_default(defaults.get((schema, table, col), ""))
        line = f"    {_bracket(col)} {type_sql}{identity_sql}{null_sql}{default_sql}"
        grouped.setdefault((schema, table), []).append(line)

    result: dict[str, str] = {}
    for (schema, table), cols in grouped.items():
        body = ",\n".join(cols)
        ddl = f"CREATE TABLE {_qident(schema, table)} (\n{body}\n);"
        key = make_object_key("TABLE", schema, table)
        result[key] = ddl
    return result


def _fetch_constraint_columns(conn: AzureConnection) -> dict[int, list[str]]:
    """Map key-constraint object_id -> ordered column names (PK / unique keys)."""
    sql = """
SELECT
    k.object_id AS CONSTRAINT_OBJECT_ID,
    c.name AS COLUMN_NAME,
    ic.key_ordinal
FROM sys.key_constraints k
JOIN sys.index_columns ic
    ON ic.object_id = k.parent_object_id
   AND ic.index_id = k.unique_index_id
JOIN sys.columns c
    ON c.object_id = ic.object_id
   AND c.column_id = ic.column_id
WHERE k.type IN ('PK', 'UQ')
  AND ic.is_included_column = 0
ORDER BY k.object_id, ic.key_ordinal
"""
    cols: dict[int, list[str]] = {}
    for row in _rows(_fetch(conn, sql)):
        cid = int(row.get("CONSTRAINT_OBJECT_ID", 0))
        cols.setdefault(cid, []).append(str(row.get("COLUMN_NAME", "")))
    return cols


def fetch_constraints(conn: AzureConnection) -> dict[str, str]:
    col_map = _fetch_constraint_columns(conn)
    result: dict[str, str] = {}

    pk_sql = """
SELECT
    k.name AS CONSTRAINT_NAME,
    s.name AS SCHEMA_NAME,
    t.name AS TABLE_NAME,
    k.object_id AS CONSTRAINT_OBJECT_ID
FROM sys.key_constraints k
JOIN sys.tables t ON k.parent_object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE k.type = 'PK'
"""
    for row in _rows(_fetch(conn, pk_sql)):
        schema = str(row.get("SCHEMA_NAME", ""))
        table = str(row.get("TABLE_NAME", ""))
        name = str(row.get("CONSTRAINT_NAME", ""))
        oid = int(row.get("CONSTRAINT_OBJECT_ID", 0))
        cols = ", ".join(_bracket(c) for c in col_map.get(oid, []))
        ddl = (
            f"ALTER TABLE {_qident(schema, table)} ADD CONSTRAINT {_bracket(name)} "
            f"PRIMARY KEY ({cols});"
        )
        key = make_object_key("CONSTRAINT", schema, name, table)
        result[key] = ddl

    fk_sql = """
SELECT
    fk.name AS CONSTRAINT_NAME,
    ps.name AS SCHEMA_NAME,
    pt.name AS TABLE_NAME,
    rs.name AS REF_SCHEMA,
    rt.name AS REF_TABLE,
    fk.object_id AS CONSTRAINT_OBJECT_ID,
    fk.delete_referential_action_desc AS DELETE_ACTION,
    fk.update_referential_action_desc AS UPDATE_ACTION
FROM sys.foreign_keys fk
JOIN sys.tables pt ON fk.parent_object_id = pt.object_id
JOIN sys.schemas ps ON pt.schema_id = ps.schema_id
JOIN sys.tables rt ON fk.referenced_object_id = rt.object_id
JOIN sys.schemas rs ON rt.schema_id = rs.schema_id
"""
    ref_cols_sql = """
SELECT
    fk.object_id,
    pc.name AS PARENT_COL,
    rc.name AS REF_COL,
    fkc.constraint_column_id
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
JOIN sys.columns pc ON fkc.parent_object_id = pc.object_id AND fkc.parent_column_id = pc.column_id
JOIN sys.columns rc ON fkc.referenced_object_id = rc.object_id AND fkc.referenced_column_id = rc.column_id
ORDER BY fk.object_id, fkc.constraint_column_id
"""
    ref_map: dict[int, tuple[list[str], list[str]]] = {}
    for row in _rows(_fetch(conn, ref_cols_sql)):
        oid = int(row.get("OBJECT_ID", 0))
        parent_cols, ref_cols = ref_map.get(oid, ([], []))
        parent_cols.append(str(row.get("PARENT_COL", "")))
        ref_cols.append(str(row.get("REF_COL", "")))
        ref_map[oid] = (parent_cols, ref_cols)

    for row in _rows(_fetch(conn, fk_sql)):
        schema = str(row.get("SCHEMA_NAME", ""))
        table = str(row.get("TABLE_NAME", ""))
        name = str(row.get("CONSTRAINT_NAME", ""))
        ref_schema = str(row.get("REF_SCHEMA", ""))
        ref_table = str(row.get("REF_TABLE", ""))
        oid = int(row.get("CONSTRAINT_OBJECT_ID", 0))
        delete_action = str(row.get("DELETE_ACTION", "NO_ACTION")).replace("_", " ")
        update_action = str(row.get("UPDATE_ACTION", "NO_ACTION")).replace("_", " ")
        parent_cols, ref_cols = ref_map.get(oid, ([], []))
        pcols = ", ".join(_bracket(c) for c in parent_cols)
        rcols = ", ".join(_bracket(c) for c in ref_cols)
        ddl = (
            f"ALTER TABLE {_qident(schema, table)} ADD CONSTRAINT {_bracket(name)} "
            f"FOREIGN KEY ({pcols}) REFERENCES {_qident(ref_schema, ref_table)} ({rcols}) "
            f"ON DELETE {delete_action} ON UPDATE {update_action};"
        )
        key = make_object_key("CONSTRAINT", schema, name, table)
        result[key] = ddl

    chk_sql = """
SELECT
    cc.name AS CONSTRAINT_NAME,
    s.name AS SCHEMA_NAME,
    t.name AS TABLE_NAME,
    cc.definition AS DEFINITION
FROM sys.check_constraints cc
JOIN sys.tables t ON cc.parent_object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
"""
    for row in _rows(_fetch(conn, chk_sql)):
        schema = str(row.get("SCHEMA_NAME", ""))
        table = str(row.get("TABLE_NAME", ""))
        name = str(row.get("CONSTRAINT_NAME", ""))
        definition = str(row.get("DEFINITION", "")).strip()
        ddl = (
            f"ALTER TABLE {_qident(schema, table)} ADD CONSTRAINT {_bracket(name)} "
            f"CHECK {definition};"
        )
        key = make_object_key("CONSTRAINT", schema, name, table)
        result[key] = ddl

    return result


def fetch_indexes(conn: AzureConnection) -> dict[str, str]:
    sql = """
SELECT
    s.name AS SCHEMA_NAME,
    t.name AS TABLE_NAME,
    i.name AS INDEX_NAME,
    i.is_unique,
    i.type_desc,
    c.name AS COLUMN_NAME,
    ic.is_descending_key,
    ic.key_ordinal
FROM sys.indexes i
JOIN sys.tables t ON i.object_id = t.object_id
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
WHERE i.is_primary_key = 0 AND i.is_unique_constraint = 0 AND i.type > 0
ORDER BY s.name, t.name, i.name, ic.key_ordinal
"""
    grouped: dict[tuple[str, str, str], dict] = {}
    for row in _rows(_fetch(conn, sql)):
        schema = str(row.get("SCHEMA_NAME", ""))
        table = str(row.get("TABLE_NAME", ""))
        index = str(row.get("INDEX_NAME", ""))
        key = (schema, table, index)
        entry = grouped.setdefault(
            key,
            {
                "unique": bool(row.get("IS_UNIQUE")),
                "type_desc": str(row.get("TYPE_DESC", "")),
                "cols": [],
            },
        )
        col = str(row.get("COLUMN_NAME", ""))
        desc = "DESC" if row.get("IS_DESCENDING_KEY") else "ASC"
        entry["cols"].append(f"{_bracket(col)} {desc}")

    result: dict[str, str] = {}
    for (schema, table, index), meta in grouped.items():
        unique = "UNIQUE " if meta["unique"] else ""
        clustered = "CLUSTERED " if "CLUSTERED" in meta["type_desc"] and "NON" not in meta["type_desc"] else "NONCLUSTERED "
        cols = ",\n    ".join(meta["cols"])
        ddl = (
            f"CREATE {unique}{clustered}INDEX {_bracket(index)}\n"
            f"ON {_qident(schema, table)}\n(\n    {cols}\n);"
        )
        obj_key = make_object_key("INDEX", schema, index, table)
        result[obj_key] = ddl
    return result


def _fetch_module_objects(conn: AzureConnection, object_type: str) -> dict[str, str]:
    type_map = {
        "PROCEDURE": "P",
        "FUNCTION": "FN",
        "VIEW": "V",
        "TRIGGER": "TR",
    }
    type_code = type_map.get(object_type)
    if not type_code:
        return {}
    if object_type == "FUNCTION":
        filter_sql = "o.type IN ('FN', 'IF', 'TF')"
    elif object_type == "TRIGGER":
        filter_sql = "o.type = 'TR'"
    else:
        filter_sql = f"o.type = '{type_code}'"

    sql = f"""
SELECT
    s.name AS SCHEMA_NAME,
    o.name AS OBJECT_NAME,
    m.definition AS DEFINITION
FROM sys.objects o
JOIN sys.schemas s ON o.schema_id = s.schema_id
JOIN sys.sql_modules m ON o.object_id = m.object_id
WHERE {filter_sql}
ORDER BY s.name, o.name
"""
    result: dict[str, str] = {}
    for row in _rows(_fetch(conn, sql)):
        schema = str(row.get("SCHEMA_NAME", ""))
        name = str(row.get("OBJECT_NAME", ""))
        definition = str(row.get("DEFINITION", "") or "").strip()
        if not definition:
            continue
        key = make_object_key(object_type, schema, name)
        result[key] = definition
    return result


def fetch_sequences(conn: AzureConnection) -> dict[str, str]:
    sql = """
SELECT
    s.name AS SCHEMA_NAME,
    seq.name AS SEQUENCE_NAME,
    ty.name AS TYPE_NAME,
    seq.start_value,
    seq.increment,
    seq.minimum_value,
    seq.maximum_value
FROM sys.sequences seq
JOIN sys.schemas s ON seq.schema_id = s.schema_id
JOIN sys.types ty ON seq.user_type_id = ty.user_type_id
ORDER BY s.name, seq.name
"""
    result: dict[str, str] = {}
    for row in _rows(_fetch(conn, sql)):
        schema = str(row.get("SCHEMA_NAME", ""))
        name = str(row.get("SEQUENCE_NAME", ""))
        type_name = str(row.get("TYPE_NAME", "")).upper()
        ddl = (
            f"CREATE SEQUENCE {_qident(schema, name)} AS {type_name} "
            f"START WITH {row.get('START_VALUE')} INCREMENT BY {row.get('INCREMENT')};"
        )
        key = make_object_key("SEQUENCE", schema, name)
        result[key] = ddl
    return result


def fetch_mqt_objects(conn: AzureConnection, object_type: str) -> dict[str, str]:
    """Fetch indexed views — SQL Server equivalent of DB2 materialized query tables."""
    sql = """
SELECT
    s.name AS SCHEMA_NAME,
    v.name AS VIEW_NAME,
    m.definition AS DEFINITION
FROM sys.views v
JOIN sys.schemas s ON v.schema_id = s.schema_id
JOIN sys.sql_modules m ON v.object_id = m.object_id
WHERE EXISTS (
    SELECT 1
    FROM sys.indexes i
    WHERE i.object_id = v.object_id
      AND i.index_id > 0
)
ORDER BY s.name, v.name
"""
    result: dict[str, str] = {}
    for row in _rows(_fetch(conn, sql)):
        schema = str(row.get("SCHEMA_NAME", ""))
        name = str(row.get("VIEW_NAME", ""))
        definition = str(row.get("DEFINITION", "") or "").strip()
        if not definition:
            continue
        key = make_object_key(object_type, schema, name)
        result[key] = definition
    return result


_FETCHERS = {
    "SCHEMA": fetch_schemas,
    "ROLE": fetch_roles,
    "TABLE": fetch_tables,
    "CONSTRAINT": fetch_constraints,
    "INDEX": fetch_indexes,
    "PROCEDURE": lambda c: _fetch_module_objects(c, "PROCEDURE"),
    "FUNCTION": lambda c: _fetch_module_objects(c, "FUNCTION"),
    "VIEW": lambda c: _fetch_module_objects(c, "VIEW"),
    "TRIGGER": lambda c: _fetch_module_objects(c, "TRIGGER"),
    "SEQUENCE": fetch_sequences,
    "MQT_IMMEDIATE": lambda c: fetch_mqt_objects(c, "MQT_IMMEDIATE"),
    "MQT_DEFERRED": lambda c: fetch_mqt_objects(c, "MQT_DEFERRED"),
}


def fetch_all_objects(conn: AzureConnection, types: list[str]) -> tuple[dict[str, dict[str, str]], str]:
    """Return {object_type: {object_key: ddl}} and optional error message."""
    result: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    for object_type in types:
        fetcher = _FETCHERS.get(object_type)
        if not fetcher:
            result[object_type] = {}
            continue
        try:
            result[object_type] = fetcher(conn)
        except Exception as exc:
            errors.append(f"{object_type}: {exc}")
            result[object_type] = {}
    err = "; ".join(errors)
    return result, err
