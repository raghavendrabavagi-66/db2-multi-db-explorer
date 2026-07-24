"""Parse deployment SQL files into comparable objects."""

from __future__ import annotations

import re
from dataclasses import dataclass

OBJECT_TYPE_FILES: dict[str, str] = {
    "SCHEMA": "01_schema.sql",
    "SEQUENCE": "02_sequence.sql",
    "TABLE": "03_table.sql",
    "CONSTRAINT": "04_constraints.sql",
    "INDEX": "05_index.sql",
    "VIEW": "06_view.sql",
    "FUNCTION": "07_function.sql",
    "PROCEDURE": "08_procedure.sql",
    "MQT_IMMEDIATE": "09_mqt_immediate.sql",
    "MQT_DEFERRED": "10_mqt_deferred.sql",
    "TRIGGER": "11_trigger.sql",
    "ROLE": "12_role.sql",
}

FILE_TO_OBJECT_TYPE: dict[str, str] = {v: k for k, v in OBJECT_TYPE_FILES.items()}


@dataclass
class DeploymentObject:
    object_type: str
    schema: str
    name: str
    parent: str
    ddl: str
    source_file: str
    start_line: int

    @property
    def object_key(self) -> str:
        return make_object_key(self.object_type, self.schema, self.name, self.parent)


def make_object_key(object_type: str, schema: str, name: str, parent: str = "") -> str:
    schema_u = (schema or "").strip().lower()
    name_u = (name or "").strip().lower()
    parent_u = (parent or "").strip().lower()
    if object_type == "SCHEMA":
        return f"schema::{name_u}"
    if object_type == "ROLE":
        return f"role::{name_u}"
    if object_type in ("TABLE", "VIEW", "PROCEDURE", "FUNCTION", "SEQUENCE"):
        return f"{object_type.lower()}::{schema_u}.{name_u}"
    if object_type in ("CONSTRAINT", "INDEX"):
        return f"{object_type.lower()}::{schema_u}.{parent_u}::{name_u}"
    if object_type == "TRIGGER":
        return f"trigger::{schema_u}.{name_u}"
    if object_type.startswith("MQT"):
        return f"mqt::{schema_u}.{name_u}"
    return f"{object_type.lower()}::{schema_u}.{name_u}"


def _line_number(full_text: str, index: int) -> int:
    return full_text[:index].count("\n") + 1


def _strip_brackets(identifier: str) -> str:
    s = identifier.strip()
    if s.startswith("[") and s.endswith("]"):
        return s[1:-1]
    return s


def _ddl_from_batch(batch: str) -> str:
    """Return batch text starting at the first SQL statement (skip leading comments)."""
    lines: list[str] = []
    started = False
    for line in batch.splitlines():
        stripped = line.strip()
        if not started:
            if not stripped or stripped.startswith("--"):
                continue
            started = True
        lines.append(line)
    return "\n".join(lines).strip()


def _batch_ddl_start_line(full_sql: str, batch_offset: int, batch: str) -> int:
    """Line number in full_sql where the first SQL statement of the batch begins."""
    trimmed = _ddl_from_batch(batch)
    if not trimmed:
        return _line_number(full_sql, batch_offset)
    first_line = trimmed.splitlines()[0].strip()
    idx = batch.find(first_line)
    if idx >= 0:
        return _line_number(full_sql, batch_offset + idx)
    return _line_number(full_sql, batch_offset)


def split_batches(sql: str) -> list[tuple[str, int]]:
    """Split SQL on GO batch separators; return (batch_text, char_offset)."""
    if not sql.strip():
        return []
    batches: list[tuple[str, int]] = []
    go_pattern = re.compile(r"(?mi)^\s*GO\s*$", re.MULTILINE)
    last = 0
    for match in go_pattern.finditer(sql):
        chunk = sql[last : match.start()].strip()
        if chunk:
            lines = [ln for ln in chunk.splitlines() if ln.strip() and not ln.strip().startswith("--")]
            if lines:
                batches.append((chunk, last))
        last = match.end()
    tail = sql[last:].strip()
    if tail:
        lines = [ln for ln in tail.splitlines() if ln.strip() and not ln.strip().startswith("--")]
        if lines:
            batches.append((tail, last))
    return batches


def _parse_schema(batch: str, source_file: str, start_line: int) -> DeploymentObject | None:
    m = re.search(
        r"CREATE\s+SCHEMA\s+(\[[^\]]+\]|\w+)",
        batch,
        re.IGNORECASE,
    )
    if not m:
        return None
    name = _strip_brackets(m.group(1))
    return DeploymentObject("SCHEMA", "", name, "", _ddl_from_batch(batch), source_file, start_line)


def _parse_table(batch: str, source_file: str, start_line: int) -> DeploymentObject | None:
    m = re.search(
        r"CREATE\s+TABLE\s+(\[[^\]]+\]|\w+)\.(\[[^\]]+\]|\w+)",
        batch,
        re.IGNORECASE,
    )
    if not m:
        return None
    schema = _strip_brackets(m.group(1))
    name = _strip_brackets(m.group(2))
    return DeploymentObject("TABLE", schema, name, "", _ddl_from_batch(batch), source_file, start_line)


def _parse_constraint(batch: str, source_file: str, start_line: int) -> DeploymentObject | None:
    m = re.search(
        r"ALTER\s+TABLE\s+(\[[^\]]+\]|\w+)\.(\[[^\]]+\]|\w+)\s+ADD\s+CONSTRAINT\s+(\[[^\]]+\]|\w+)",
        batch,
        re.IGNORECASE,
    )
    if not m:
        return None
    schema = _strip_brackets(m.group(1))
    table = _strip_brackets(m.group(2))
    name = _strip_brackets(m.group(3))
    return DeploymentObject("CONSTRAINT", schema, name, table, _ddl_from_batch(batch), source_file, start_line)


def _parse_index(batch: str, source_file: str, start_line: int) -> DeploymentObject | None:
    if re.search(r"^\s*IF\s+EXISTS", batch, re.IGNORECASE | re.MULTILINE) and not re.search(
        r"CREATE\s+(?:UNIQUE\s+)?(?:NONCLUSTERED\s+)?INDEX", batch, re.IGNORECASE
    ):
        return None
    m = re.search(
        r"CREATE\s+(?:UNIQUE\s+)?(?:NONCLUSTERED\s+|CLUSTERED\s+)?INDEX\s+(\[[^\]]+\]|\w+)\s+ON\s+(\[[^\]]+\]|\w+)\.(\[[^\]]+\]|\w+)",
        batch,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    name = _strip_brackets(m.group(1))
    schema = _strip_brackets(m.group(2))
    table = _strip_brackets(m.group(3))
    return DeploymentObject("INDEX", schema, name, table, _ddl_from_batch(batch), source_file, start_line)


def _parse_procedure(batch: str, source_file: str, start_line: int, kind: str) -> DeploymentObject | None:
    pattern = (
        r"CREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\s+(\[[^\]]+\]|\w+)\.(\[[^\]]+\]|\w+)"
        if kind == "PROCEDURE"
        else r"CREATE\s+(?:OR\s+ALTER\s+)?FUNCTION\s+(\[[^\]]+\]|\w+)\.(\[[^\]]+\]|\w+)"
    )
    m = re.search(pattern, batch, re.IGNORECASE)
    if not m:
        return None
    schema = _strip_brackets(m.group(1))
    name = _strip_brackets(m.group(2))
    return DeploymentObject(kind, schema, name, "", _ddl_from_batch(batch), source_file, start_line)


def _parse_view(batch: str, source_file: str, start_line: int) -> DeploymentObject | None:
    m = re.search(
        r"CREATE\s+(?:OR\s+ALTER\s+)?VIEW\s+(\[[^\]]+\]|\w+)\.(\[[^\]]+\]|\w+)",
        batch,
        re.IGNORECASE,
    )
    if not m:
        return None
    schema = _strip_brackets(m.group(1))
    name = _strip_brackets(m.group(2))
    return DeploymentObject("VIEW", schema, name, "", _ddl_from_batch(batch), source_file, start_line)


def _parse_sequence(batch: str, source_file: str, start_line: int) -> DeploymentObject | None:
    m = re.search(
        r"CREATE\s+SEQUENCE\s+(\[[^\]]+\]|\w+)\.(\[[^\]]+\]|\w+)",
        batch,
        re.IGNORECASE,
    )
    if not m:
        return None
    schema = _strip_brackets(m.group(1))
    name = _strip_brackets(m.group(2))
    return DeploymentObject("SEQUENCE", schema, name, "", _ddl_from_batch(batch), source_file, start_line)


def _parse_trigger(batch: str, source_file: str, start_line: int) -> DeploymentObject | None:
    m = re.search(
        r"CREATE\s+TRIGGER\s+(\[[^\]]+\]|\w+)\.(\[[^\]]+\]|\w+)\s+ON\s+(\[[^\]]+\]|\w+)\.(\[[^\]]+\]|\w+)",
        batch,
        re.IGNORECASE,
    )
    if not m:
        return None
    schema = _strip_brackets(m.group(1))
    name = _strip_brackets(m.group(2))
    table = _strip_brackets(m.group(4))
    return DeploymentObject("TRIGGER", schema, name, table, _ddl_from_batch(batch), source_file, start_line)


def _parse_role(batch: str, source_file: str, start_line: int) -> DeploymentObject | None:
    m = re.search(r"CREATE\s+ROLE\s+(\[[^\]]+\]|\w+)", batch, re.IGNORECASE)
    if not m:
        return None
    name = _strip_brackets(m.group(1))
    return DeploymentObject("ROLE", "", name, "", _ddl_from_batch(batch), source_file, start_line)


def _parse_mqt(batch: str, source_file: str, start_line: int, kind: str) -> DeploymentObject | None:
    obj = _parse_table(batch, source_file, start_line)
    if obj:
        return DeploymentObject(kind, obj.schema, obj.name, "", _ddl_from_batch(batch), source_file, start_line)
    return None


def _parser_for_type(object_type: str):
    def _wrap(batch, source_file, start_line):
        if object_type == "SCHEMA":
            return _parse_schema(batch, source_file, start_line)
        if object_type == "TABLE":
            return _parse_table(batch, source_file, start_line)
        if object_type == "CONSTRAINT":
            return _parse_constraint(batch, source_file, start_line)
        if object_type == "INDEX":
            return _parse_index(batch, source_file, start_line)
        if object_type == "PROCEDURE":
            return _parse_procedure(batch, source_file, start_line, "PROCEDURE")
        if object_type == "FUNCTION":
            return _parse_procedure(batch, source_file, start_line, "FUNCTION")
        if object_type == "VIEW":
            return _parse_view(batch, source_file, start_line)
        if object_type == "SEQUENCE":
            return _parse_sequence(batch, source_file, start_line)
        if object_type == "TRIGGER":
            return _parse_trigger(batch, source_file, start_line)
        if object_type == "ROLE":
            return _parse_role(batch, source_file, start_line)
        if object_type in ("MQT_IMMEDIATE", "MQT_DEFERRED"):
            return _parse_mqt(batch, source_file, start_line, object_type)
        return None

    return _wrap


def parse_deployment_file(content: str, filename: str) -> list[DeploymentObject]:
    object_type = FILE_TO_OBJECT_TYPE.get(filename)
    if not object_type:
        return []
    parser = _parser_for_type(object_type)
    objects: list[DeploymentObject] = []
    for batch, batch_offset in split_batches(content):
        start_line = _batch_ddl_start_line(content, batch_offset, batch)
        obj = parser(batch, filename, start_line)
        if obj:
            objects.append(obj)
    return objects


def parse_all_deployment_files(files: dict[str, str]) -> dict[str, list[DeploymentObject]]:
    """Parse fetched GitLab files into objects keyed by object type."""
    result: dict[str, list[DeploymentObject]] = {t: [] for t in OBJECT_TYPE_FILES}
    for object_type, filename in OBJECT_TYPE_FILES.items():
        content = files.get(filename)
        if content:
            result[object_type] = parse_deployment_file(content, filename)
    return result
