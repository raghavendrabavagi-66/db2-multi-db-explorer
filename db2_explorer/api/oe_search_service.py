"""Execute Object Explorer fleet search and return JSON for the iframe API."""

from __future__ import annotations

from typing import Any

from db2_explorer.clients.db2 import run_across_databases
from db2_explorer.data.connections import Connection, connections_from_rows
from db2_explorer.data.queries import MATCH_ORDER, OBJECT_TYPES
from db2_explorer.ui.oe_results import search_response_payload


def _parse_fleet(raw: Any) -> list[tuple[str, str, int]]:
    if not isinstance(raw, list):
        return []
    parsed: list[tuple[str, str, int]] = []
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        db, host = str(row[0]).strip(), str(row[1]).strip()
        if not db or not host:
            continue
        try:
            port = int(row[2]) if len(row) > 2 else 50000
        except (TypeError, ValueError):
            port = 50000
        parsed.append((db, host, port))
    return parsed


def execute_search_json(body: dict[str, Any]) -> dict[str, Any]:
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    if not username or not password:
        return {"ok": False, "error": "Username and password are required."}

    fleet = _parse_fleet(body.get("fleet"))
    connections: list[Connection] = connections_from_rows(fleet)
    if not connections:
        return {"ok": False, "error": "Add at least one database to the fleet."}

    object_type = str(body.get("object_type") or OBJECT_TYPES[0])
    if object_type not in OBJECT_TYPES:
        object_type = OBJECT_TYPES[0]

    operator = str(body.get("operator") or MATCH_ORDER[0])
    if operator not in MATCH_ORDER:
        operator = MATCH_ORDER[0]

    filter_text = str(body.get("filter_text") or "")
    include_system = bool(body.get("include_system"))
    try:
        max_workers = int(body.get("max_workers") or 8)
    except (TypeError, ValueError):
        max_workers = 8

    results = run_across_databases(
        connections,
        username,
        password,
        object_type,
        operator,
        filter_text,
        include_system=include_system,
        max_workers=max_workers,
    )
    last_meta = {
        "object_type": object_type,
        "operator": operator,
        "text": filter_text,
        "scan_time_ms": sum(r.elapsed_ms for r in results),
    }
    payload = search_response_payload(
        results,
        object_type=object_type,
        operator=operator,
        filter_text=filter_text,
        last_meta=last_meta,
    )
    return payload
