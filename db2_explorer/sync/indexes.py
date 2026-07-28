"""Generate and apply index sync scripts (GitLab deployment -> target database)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from db2_explorer.clients.azure import AzureConnection, AzureExecuteOutcome, execute_batch, query
from db2_explorer.ddl.normalizer import strip_comments_and_headers
from db2_explorer.compare.schema_compare import ObjectCompareResult

IndexKind = Literal["NONCLUSTERED", "UNIQUE", "CLUSTERED", "UNKNOWN"]
SyncAction = Literal["create", "replace", "drop_only", "none"]

_CREATE_INDEX_RE = re.compile(
    r"CREATE\s+(?P<unique>UNIQUE\s+)?(?P<clustered>NONCLUSTERED\s+|CLUSTERED\s+)?INDEX\s+",
    re.IGNORECASE,
)


@dataclass
class IndexSyncScript:
    steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    kind: IndexKind = "UNKNOWN"
    action: SyncAction = "none"
    message: str = ""

    @property
    def sql_text(self) -> str:
        return "\n\n".join(self.steps)


@dataclass
class PreflightResult:
    ok: bool = True
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ApplyOutcome:
    ok: bool = True
    error: str = ""
    executed_sql: list[str] = field(default_factory=list)


def _bracket(name: str) -> str:
    return f"[{name.replace(']', ']]')}]"


def _qident(schema: str, name: str) -> str:
    return f"{_bracket(schema)}.{_bracket(name)}"


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def classify_index(ddl: str) -> IndexKind:
    text = strip_comments_and_headers(ddl or "")
    one_line = re.sub(r"\s+", " ", text).strip().upper()
    if not one_line or "CREATE" not in one_line or "INDEX" not in one_line:
        return "UNKNOWN"
    m = _CREATE_INDEX_RE.search(one_line)
    if not m:
        return "UNKNOWN"
    if m.group("unique"):
        return "UNIQUE"
    clustered = (m.group("clustered") or "").strip().upper()
    if clustered.startswith("CLUSTERED"):
        return "CLUSTERED"
    return "NONCLUSTERED"


def clean_executable_create_ddl(gitlab_ddl: str) -> str:
    """Return a single executable CREATE INDEX statement from GitLab batch text."""
    text = strip_comments_and_headers(gitlab_ddl or "")
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"(?i)^GO$", stripped):
            continue
        if re.match(r"(?i)^IF\s+EXISTS", stripped):
            continue
        if re.match(r"(?i)^DROP\s+INDEX", stripped):
            continue
        lines.append(stripped)
    if not lines:
        return ""
    ddl = " ".join(lines).strip()
    if not re.search(r"(?i)CREATE\s+(?:UNIQUE\s+)?(?:NONCLUSTERED\s+|CLUSTERED\s+)?INDEX", ddl):
        return ""
    if not ddl.endswith(";"):
        ddl += ";"
    return ddl


def generate_if_exists_drop_sql(schema: str, table: str, index_name: str) -> str:
    schema_lit = _escape_sql_literal(schema)
    table_lit = _escape_sql_literal(table)
    index_lit = _escape_sql_literal(index_name)
    return (
        f"IF EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'{index_lit}' "
        f"AND object_id = OBJECT_ID(N'{_bracket(schema)}.{_bracket(table)}')) "
        f"DROP INDEX {_bracket(index_name)} ON {_qident(schema, table)};"
    )


def generate_drop_sql(schema: str, table: str, index_name: str) -> str:
    return f"DROP INDEX {_bracket(index_name)} ON {_qident(schema, table)};"


def _object_id_sql(schema: str, table: str) -> str:
    return f"OBJECT_ID(N'{_escape_sql_literal(schema)}.{_escape_sql_literal(table)}', N'U')"


def _warnings_for_kind(kind: IndexKind, action: SyncAction) -> list[str]:
    warnings: list[str] = []
    if action in ("create", "replace"):
        warnings.append(
            "Dropping and recreating an index may lock the table and rebuild the index "
            "on large tables."
        )
    if kind == "UNIQUE" and action in ("create", "replace"):
        warnings.append(
            "Recreating a UNIQUE index will fail if duplicate key values exist in the table."
        )
    return warnings


def generate_index_sync_script(item: ObjectCompareResult) -> IndexSyncScript:
    """Build sync SQL for an index compare result."""
    if item.object_type != "INDEX":
        return IndexSyncScript(action="none", message="Not an index object.")

    if item.status == "identical":
        return IndexSyncScript(action="none", message="Definitions already match.")

    if item.status == "only_db":
        drop = generate_drop_sql(item.schema, item.parent, item.name)
        return IndexSyncScript(
            steps=[drop],
            kind=classify_index(item.db_ddl),
            action="drop_only",
            message="Suggested DROP script (not executed from GitLab sync).",
        )

    create_ddl = clean_executable_create_ddl(item.gitlab_ddl)
    if not create_ddl:
        return IndexSyncScript(
            action="none",
            message="GitLab CREATE INDEX DDL is empty or could not be parsed.",
            warnings=["Cannot generate sync script without GitLab CREATE INDEX text."],
        )

    if not item.parent or not item.name:
        return IndexSyncScript(action="none", message="Missing table or index name.")

    kind = classify_index(item.gitlab_ddl)
    if_exists_drop = generate_if_exists_drop_sql(item.schema, item.parent, item.name)

    if item.status == "only_gitlab":
        return IndexSyncScript(
            steps=[if_exists_drop, create_ddl],
            kind=kind,
            action="create",
            warnings=_warnings_for_kind(kind, "create"),
        )

    if item.status == "different":
        return IndexSyncScript(
            steps=[if_exists_drop, create_ddl],
            kind=kind,
            action="replace",
            warnings=_warnings_for_kind(kind, "replace"),
        )

    return IndexSyncScript(action="none", message=f"Unsupported status: {item.status}")


def order_index_sync(items: list[ObjectCompareResult]) -> list[ObjectCompareResult]:
    """Order index sync items alphabetically by schema, table, index name."""
    applicable = [
        i
        for i in items
        if i.object_type == "INDEX"
        and i.status in ("only_gitlab", "different")
        and clean_executable_create_ddl(i.gitlab_ddl)
    ]
    return sorted(applicable, key=lambda i: (i.schema.lower(), i.parent.lower(), i.name.lower()))


def preflight_index(
    conn: AzureConnection,
    item: ObjectCompareResult,
    script: IndexSyncScript,
) -> PreflightResult:
    """Run catalog checks before applying an index sync script."""
    result = PreflightResult()
    if not script.steps or script.action not in ("create", "replace"):
        return result

    if not item.parent:
        result.ok = False
        result.blockers.append("Missing parent table name.")
        return result

    table_check = query(
        conn,
        f"SELECT CASE WHEN {_object_id_sql(item.schema, item.parent)} IS NOT NULL "
        f"THEN 1 ELSE 0 END AS EXISTS_FLAG",
    )
    if not table_check.ok:
        result.ok = False
        result.blockers.append(f"Could not verify table: {table_check.error}")
        return result
    if not table_check.rows or int(table_check.rows[0].get("EXISTS_FLAG", 0)) != 1:
        result.ok = False
        result.blockers.append(f"Table {item.schema}.{item.parent} does not exist in the database.")
        return result

    if script.action == "replace":
        index_lit = _escape_sql_literal(item.name)
        schema_lit = _escape_sql_literal(item.schema)
        table_lit = _escape_sql_literal(item.parent)
        index_check = query(
            conn,
            f"""
SELECT CASE WHEN EXISTS (
    SELECT 1 FROM sys.indexes i
    INNER JOIN sys.tables t ON i.object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = N'{schema_lit}'
      AND t.name = N'{table_lit}'
      AND i.name = N'{index_lit}'
      AND i.type > 0
) THEN 1 ELSE 0 END AS EXISTS_FLAG
""",
        )
        if index_check.ok and index_check.rows:
            if int(index_check.rows[0].get("EXISTS_FLAG", 0)) != 1:
                result.warnings.append(
                    f"Index {item.name} was not found in catalog; IF EXISTS drop will skip."
                )

    for w in script.warnings:
        if w not in result.warnings:
            result.warnings.append(w)

    return result


def apply_index_sync_script(conn: AzureConnection, script: IndexSyncScript) -> ApplyOutcome:
    """Execute an index sync script in a single transaction."""
    if script.action not in ("create", "replace"):
        return ApplyOutcome(ok=False, error=script.message or "Nothing to apply.")
    if not script.steps:
        return ApplyOutcome(ok=False, error="Sync script has no steps.")

    outcome: AzureExecuteOutcome = execute_batch(conn, script.steps)
    if outcome.ok:
        return ApplyOutcome(ok=True, executed_sql=outcome.executed_sql)
    return ApplyOutcome(ok=False, error=outcome.error, executed_sql=outcome.executed_sql)


def generate_index_batch_scripts(
    items: list[ObjectCompareResult],
) -> list[tuple[ObjectCompareResult, IndexSyncScript]]:
    """Return ordered (item, script) pairs for batch index sync."""
    ordered = order_index_sync(items)
    result: list[tuple[ObjectCompareResult, IndexSyncScript]] = []
    for item in ordered:
        script = generate_index_sync_script(item)
        if script.action in ("create", "replace") and script.steps:
            result.append((item, script))
    return result
