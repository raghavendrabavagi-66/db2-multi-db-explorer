"""Generate and apply constraint sync scripts (GitLab deployment -> target database)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from db2_explorer.clients.azure import AzureConnection, AzureExecuteOutcome, execute_batch, query
from db2_explorer.sync.constraint_summary import parse_constraint_ddl
from db2_explorer.ddl.normalizer import strip_comments_and_headers
from db2_explorer.compare.schema_compare import ObjectCompareResult

ConstraintKind = Literal["PK", "FK", "CHECK", "UNIQUE", "DEFAULT", "UNKNOWN"]
SyncAction = Literal["create", "replace", "drop_only", "none"]

_KIND_MAP = {
    "PRIMARY KEY": "PK",
    "FOREIGN KEY": "FK",
    "CHECK": "CHECK",
    "UNIQUE": "UNIQUE",
    "DEFAULT": "DEFAULT",
}


@dataclass
class SyncScript:
    steps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    kind: ConstraintKind = "UNKNOWN"
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


def classify_constraint(ddl: str) -> ConstraintKind:
    parsed = parse_constraint_ddl(ddl)
    kind = parsed.get("kind", "UNKNOWN")
    return _KIND_MAP.get(kind, "UNKNOWN")  # type: ignore[return-value]


def clean_executable_ddl(gitlab_ddl: str) -> str:
    """Return a single executable ADD CONSTRAINT statement from GitLab batch text."""
    text = strip_comments_and_headers(gitlab_ddl or "")
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"(?i)^GO$", stripped):
            continue
        lines.append(stripped)
    if not lines:
        return ""
    ddl = " ".join(lines).strip()
    if not ddl.endswith(";"):
        ddl += ";"
    return ddl


def generate_drop_sql(schema: str, table: str, constraint_name: str) -> str:
    return (
        f"ALTER TABLE {_qident(schema, table)} DROP CONSTRAINT {_bracket(constraint_name)};"
    )


def _warnings_for_kind(kind: ConstraintKind, action: SyncAction) -> list[str]:
    warnings: list[str] = []
    if action == "replace" and kind == "PK":
        warnings.append(
            "Replacing a PRIMARY KEY may fail if other tables have foreign keys "
            "referencing this table. Drop or update those FKs first."
        )
    if action == "create" and kind == "FK":
        warnings.append(
            "Adding a FOREIGN KEY will fail if referenced keys are missing or "
            "existing rows violate the relationship."
        )
    return warnings


def generate_sync_script(item: ObjectCompareResult) -> SyncScript:
    """Build sync SQL for a constraint compare result."""
    if item.object_type != "CONSTRAINT":
        return SyncScript(action="none", message="Not a constraint object.")

    if item.status == "identical":
        return SyncScript(action="none", message="Definitions already match.")

    if item.status == "only_db":
        if not item.db_ddl.strip() and item.parent and item.name:
            drop = generate_drop_sql(item.schema, item.parent, item.name)
            return SyncScript(
                steps=[drop],
                kind=classify_constraint(item.db_ddl),
                action="drop_only",
                message="Suggested DROP script (GitLab has no definition for this constraint).",
            )
        drop = generate_drop_sql(item.schema, item.parent, item.name)
        return SyncScript(
            steps=[drop],
            kind=classify_constraint(item.db_ddl),
            action="drop_only",
            message="Suggested DROP script (not executed from GitLab sync).",
        )

    add_ddl = clean_executable_ddl(item.gitlab_ddl)
    if not add_ddl:
        return SyncScript(
            action="none",
            message="GitLab DDL is empty or could not be parsed.",
            warnings=["Cannot generate sync script without GitLab ADD CONSTRAINT text."],
        )

    kind = classify_constraint(item.gitlab_ddl)

    if item.status == "only_gitlab":
        return SyncScript(
            steps=[add_ddl],
            kind=kind,
            action="create",
            warnings=_warnings_for_kind(kind, "create"),
        )

    if item.status == "different":
        if not item.parent or not item.name:
            return SyncScript(action="none", message="Missing table or constraint name.")
        drop = generate_drop_sql(item.schema, item.parent, item.name)
        return SyncScript(
            steps=[drop, add_ddl],
            kind=kind,
            action="replace",
            warnings=_warnings_for_kind(kind, "replace"),
        )

    return SyncScript(action="none", message=f"Unsupported status: {item.status}")


def _parse_ref_table_key(ref_table: str) -> str:
    """Normalize referenced table to schema.table lowercase key."""
    text = ref_table.strip()
    m = re.match(
        r"(?:\[([^\]]+)\]|\w+)\.\[([^\]]+)\]|\[([^\]]+)\]",
        text,
        re.IGNORECASE,
    )
    if m:
        if m.group(1) and m.group(2):
            return f"{m.group(1).lower()}.{m.group(2).lower()}"
        if m.group(3):
            return f"dbo.{m.group(3).lower()}"
    if "." in text:
        parts = text.replace("[", "").replace("]", "").split(".", 1)
        return f"{parts[0].lower()}.{parts[1].lower()}"
    return f"dbo.{text.replace('[', '').replace(']', '').lower()}"


def _table_key(schema: str, table: str) -> str:
    return f"{schema.lower()}.{table.lower()}"


def _topological_sort_fk(items: list[ObjectCompareResult]) -> list[ObjectCompareResult]:
    """Order FK creates so referenced-table constraints appear before dependents."""
    if not items:
        return []

    by_key = {i.object_key: i for i in items}
    deps: dict[str, set[str]] = {i.object_key: set() for i in items}

    for item in items:
        parsed = parse_constraint_ddl(item.gitlab_ddl)
        ref = _parse_ref_table_key(parsed.get("referenced_table", ""))
        for other in items:
            if other.object_key == item.object_key:
                continue
            if _table_key(other.schema, other.parent) == ref:
                deps[item.object_key].add(other.object_key)

    ordered_keys: list[str] = []
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visited:
            return
        for dep in deps.get(key, set()):
            visit(dep)
        visited.add(key)
        ordered_keys.append(key)

    for item in items:
        visit(item.object_key)

    return [by_key[k] for k in ordered_keys]


def order_constraint_sync(items: list[ObjectCompareResult]) -> list[ObjectCompareResult]:
    """Order constraint sync items: creates (PK first, FK topo), then replaces (PK last)."""
    applicable = [
        i
        for i in items
        if i.object_type == "CONSTRAINT"
        and i.status in ("only_gitlab", "different")
        and clean_executable_ddl(i.gitlab_ddl)
    ]
    creates = [i for i in applicable if i.status == "only_gitlab"]
    replaces = [i for i in applicable if i.status == "different"]

    def kind_of(item: ObjectCompareResult) -> ConstraintKind:
        return classify_constraint(item.gitlab_ddl)

    create_non_fk = [i for i in creates if kind_of(i) != "FK"]
    create_fk = _topological_sort_fk([i for i in creates if kind_of(i) == "FK"])

    replace_non_pk = [i for i in replaces if kind_of(i) != "PK"]
    replace_pk = [i for i in replaces if kind_of(i) == "PK"]

    return create_non_fk + create_fk + replace_non_pk + replace_pk


def _object_id_sql(schema: str, name: str) -> str:
    return f"OBJECT_ID(N'{schema}.{name}', N'U')"


def preflight_constraint(
    conn: AzureConnection,
    item: ObjectCompareResult,
    script: SyncScript,
) -> PreflightResult:
    """Run catalog checks before applying a constraint sync script."""
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
        constraint_check = query(
            conn,
            f"""
SELECT CASE WHEN EXISTS (
    SELECT 1
    FROM sys.objects o
    INNER JOIN sys.tables t ON o.parent_object_id = t.object_id
    INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
    WHERE s.name = N'{item.schema.replace("'", "''")}'
      AND t.name = N'{item.parent.replace("'", "''")}'
      AND o.name = N'{item.name.replace("'", "''")}'
      AND o.type IN ('F', 'PK', 'UQ', 'C', 'D')
) THEN 1 ELSE 0 END AS EXISTS_FLAG
""",
        )
        if constraint_check.ok and constraint_check.rows:
            if int(constraint_check.rows[0].get("EXISTS_FLAG", 0)) != 1:
                result.warnings.append(
                    f"Constraint {item.name} was not found in catalog; DROP may fail."
                )

    if script.kind == "FK" and script.action == "create":
        parsed = parse_constraint_ddl(item.gitlab_ddl)
        ref = parsed.get("referenced_table", "")
        if ref:
            ref_clean = ref.replace("[", "").replace("]", "")
            if "." in ref_clean:
                ref_schema, ref_table = ref_clean.split(".", 1)
            else:
                ref_schema, ref_table = "dbo", ref_clean
            ref_check = query(
                conn,
                f"SELECT CASE WHEN {_object_id_sql(ref_schema, ref_table)} IS NOT NULL "
                f"THEN 1 ELSE 0 END AS EXISTS_FLAG",
            )
            if ref_check.ok and ref_check.rows:
                if int(ref_check.rows[0].get("EXISTS_FLAG", 0)) != 1:
                    result.ok = False
                    result.blockers.append(
                        f"Referenced table {ref_schema}.{ref_table} does not exist."
                    )

    if script.kind == "PK" and script.action == "replace":
        fk_deps = query(
            conn,
            f"""
SELECT fk.name AS FK_NAME,
       OBJECT_SCHEMA_NAME(fk.parent_object_id) AS CHILD_SCHEMA,
       OBJECT_NAME(fk.parent_object_id) AS CHILD_TABLE
FROM sys.foreign_keys fk
WHERE fk.referenced_object_id = {_object_id_sql(item.schema, item.parent)}
""",
        )
        if fk_deps.ok and fk_deps.rows:
            names = [
                f"{r.get('CHILD_SCHEMA')}.{r.get('CHILD_TABLE')}.{r.get('FK_NAME')}"
                for r in fk_deps.rows
            ]
            result.warnings.append(
                "Other tables reference this primary key: " + ", ".join(names[:5])
                + (" …" if len(names) > 5 else "")
            )
            result.warnings.append(
                "DROP PRIMARY KEY may fail until dependent foreign keys are removed."
            )

    for w in script.warnings:
        if w not in result.warnings:
            result.warnings.append(w)

    return result


def apply_sync_script(conn: AzureConnection, script: SyncScript) -> ApplyOutcome:
    """Execute a sync script in a single transaction."""
    if script.action not in ("create", "replace"):
        return ApplyOutcome(ok=False, error=script.message or "Nothing to apply.")
    if not script.steps:
        return ApplyOutcome(ok=False, error="Sync script has no steps.")

    outcome: AzureExecuteOutcome = execute_batch(conn, script.steps)
    if outcome.ok:
        return ApplyOutcome(ok=True, executed_sql=outcome.executed_sql)
    return ApplyOutcome(ok=False, error=outcome.error, executed_sql=outcome.executed_sql)


def generate_batch_scripts(items: list[ObjectCompareResult]) -> list[tuple[ObjectCompareResult, SyncScript]]:
    """Return ordered (item, script) pairs for batch constraint sync."""
    ordered = order_constraint_sync(items)
    result: list[tuple[ObjectCompareResult, SyncScript]] = []
    for item in ordered:
        script = generate_sync_script(item)
        if script.action in ("create", "replace") and script.steps:
            result.append((item, script))
    return result
