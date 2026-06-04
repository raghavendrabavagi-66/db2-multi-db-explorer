"""Maps object-type buttons and name-match operators to DB2 system-catalog SQL.

Every generated query returns the same normalized columns so results from
different object types can be unioned/stacked in a single table:

    SCHEMA, OBJECT_NAME, OBJECT_TYPE, SUB_TYPE, CREATE_TIME

The name filter is always passed as a bound parameter (``?``) -> no SQL
injection, and matching is case-insensitive via ``UPPER()``.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Name-match operators (second-level filter)
# ---------------------------------------------------------------------------

# label -> function turning the user's text into a LIKE pattern.
MATCH_OPERATORS: dict[str, "callable"] = {
    "begins with": lambda t: f"{t}%",
    "ends with": lambda t: f"%{t}",
    "anywhere": lambda t: f"%{t}%",
    "exact": lambda t: t,
}

# Order used to render UI radio buttons.
MATCH_ORDER = ["begins with", "ends with", "anywhere", "exact"]


def build_pattern(operator: str, text: str) -> str:
    """Turn an operator + raw text into an (uppercased) LIKE pattern."""
    if operator not in MATCH_OPERATORS:
        raise ValueError(f"Unknown match operator: {operator!r}")
    return MATCH_OPERATORS[operator]((text or "").upper())


# ---------------------------------------------------------------------------
# Object types -> catalog queries
# ---------------------------------------------------------------------------

OBJECT_TYPES = [
    "Table",
    "View",
    "MQT",
    "Index",
    "Sequence",
    "Alias",
    "Nickname",
    "Trigger",
    "XML Schema",
    "Application Object",
]


@dataclass(frozen=True)
class BuiltQuery:
    sql: str
    params: list[str]


def _single_view_sql(
    *,
    view: str,
    schema_col: str,
    name_col: str,
    create_col: str,
    type_label: str,
    sub_type_expr: str = "''",
    extra_where: str = "",
    include_system: bool,
) -> str:
    """Build a normalized SELECT against one catalog view.

    The query contains exactly one ``?`` (for the name LIKE pattern).
    """
    clauses = [f"UPPER({name_col}) LIKE ?"]
    if extra_where:
        clauses.append(extra_where)
    if not include_system:
        clauses.append(f"RTRIM({schema_col}) NOT LIKE 'SYS%'")
    where = " AND ".join(clauses)
    return (
        f"SELECT RTRIM({schema_col}) AS SCHEMA, "
        f"RTRIM({name_col}) AS OBJECT_NAME, "
        f"'{type_label}' AS OBJECT_TYPE, "
        f"{sub_type_expr} AS SUB_TYPE, "
        f"{create_col} AS CREATE_TIME "
        f"FROM {view} WHERE {where}"
    )


def _application_object_sql(*, include_system: bool) -> str:
    """UNION over routines (procs/functions/UDFs), modules and packages."""
    routines = _single_view_sql(
        view="SYSCAT.ROUTINES",
        schema_col="ROUTINESCHEMA",
        name_col="ROUTINENAME",
        create_col="CREATE_TIME",
        type_label="Application Object",
        sub_type_expr=(
            "CASE ROUTINETYPE "
            "WHEN 'P' THEN 'Procedure' "
            "WHEN 'F' THEN 'Function' "
            "WHEN 'M' THEN 'Method' "
            "ELSE 'Routine' END"
        ),
        include_system=include_system,
    )
    modules = _single_view_sql(
        view="SYSCAT.MODULES",
        schema_col="MODULESCHEMA",
        name_col="MODULENAME",
        create_col="CREATE_TIME",
        type_label="Application Object",
        sub_type_expr="'Module'",
        include_system=include_system,
    )
    packages = _single_view_sql(
        view="SYSCAT.PACKAGES",
        schema_col="PKGSCHEMA",
        name_col="PKGNAME",
        create_col="LAST_BIND_TIME",
        type_label="Application Object",
        sub_type_expr="'Package'",
        include_system=include_system,
    )
    return f"{routines}\nUNION ALL\n{modules}\nUNION ALL\n{packages}"


def build_query(
    object_type: str,
    operator: str,
    text: str,
    *,
    include_system: bool = False,
) -> BuiltQuery:
    """Build the full SQL + bound params for a given object type and filter."""
    if object_type not in OBJECT_TYPES:
        raise ValueError(f"Unknown object type: {object_type!r}")

    pattern = build_pattern(operator, text)

    if object_type == "Application Object":
        sql = _application_object_sql(include_system=include_system)
        # Three ``?`` placeholders (routines, modules, packages).
        return BuiltQuery(sql=sql, params=[pattern, pattern, pattern])

    # SYSCAT.TABLES-backed types share a view and differ only by TYPE.
    tables_type = {
        "Table": "T",
        "View": "V",
        "MQT": "S",
        "Alias": "A",
        "Nickname": "N",
    }
    if object_type in tables_type:
        sql = _single_view_sql(
            view="SYSCAT.TABLES",
            schema_col="TABSCHEMA",
            name_col="TABNAME",
            create_col="CREATE_TIME",
            type_label=object_type,
            extra_where=f"TYPE = '{tables_type[object_type]}'",
            include_system=include_system,
        )
        return BuiltQuery(sql=sql, params=[pattern])

    standalone = {
        "Index": ("SYSCAT.INDEXES", "INDSCHEMA", "INDNAME", "CREATE_TIME"),
        "Sequence": ("SYSCAT.SEQUENCES", "SEQSCHEMA", "SEQNAME", "CREATE_TIME"),
        "Trigger": ("SYSCAT.TRIGGERS", "TRIGSCHEMA", "TRIGNAME", "CREATE_TIME"),
        "XML Schema": ("SYSCAT.XSROBJECTS", "OBJECTSCHEMA", "OBJECTNAME", "CREATE_TIME"),
    }
    view, schema_col, name_col, create_col = standalone[object_type]
    sql = _single_view_sql(
        view=view,
        schema_col=schema_col,
        name_col=name_col,
        create_col=create_col,
        type_label=object_type,
        include_system=include_system,
    )
    return BuiltQuery(sql=sql, params=[pattern])
