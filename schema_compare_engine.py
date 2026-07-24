"""Orchestrate GitLab deployment vs live database schema comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ddl_normalizer import normalize_pair
from deployment_parser import DeploymentObject
from diff_viewer import side_by_side_diff_html

CompareStatusLiteral = Literal["identical", "different", "only_gitlab", "only_db"]


@dataclass
class CompareSummary:
    identical: int = 0
    different: int = 0
    only_gitlab: int = 0
    only_db: int = 0


@dataclass
class ObjectCompareResult:
    object_key: str
    object_type: str
    schema: str
    name: str
    parent: str
    status: CompareStatusLiteral
    gitlab_ddl: str
    db_ddl: str
    gitlab_line: int | None
    source_file: str
    diff_html: str = ""


@dataclass
class SchemaCompareResult:
    by_type: dict[str, list[ObjectCompareResult]] = field(default_factory=dict)
    summary: CompareSummary = field(default_factory=CompareSummary)
    missing_files: list[str] = field(default_factory=list)
    bundle_path: str = ""


def run_schema_compare(
    gitlab_objects: dict[str, list[DeploymentObject]],
    db_objects: dict[str, dict[str, str]],
) -> SchemaCompareResult:
    result = SchemaCompareResult()
    summary = CompareSummary()

    all_types = sorted(set(gitlab_objects.keys()) | set(db_objects.keys()))
    for object_type in all_types:
        gl_list = gitlab_objects.get(object_type, [])
        db_map = db_objects.get(object_type, {})

        gl_by_key = {obj.object_key: obj for obj in gl_list}
        all_keys = sorted(set(gl_by_key.keys()) | set(db_map.keys()))
        type_results: list[ObjectCompareResult] = []

        for key in all_keys:
            gl_obj = gl_by_key.get(key)
            db_ddl = db_map.get(key, "")

            if gl_obj and db_ddl:
                _, _, is_match = normalize_pair(gl_obj.ddl, db_ddl, object_type)
                status: CompareStatusLiteral = "identical" if is_match else "different"
                diff_html = side_by_side_diff_html(gl_obj.ddl, db_ddl)
                type_results.append(
                    ObjectCompareResult(
                        object_key=key,
                        object_type=object_type,
                        schema=gl_obj.schema,
                        name=gl_obj.name,
                        parent=gl_obj.parent,
                        status=status,
                        gitlab_ddl=gl_obj.ddl,
                        db_ddl=db_ddl,
                        gitlab_line=gl_obj.start_line,
                        source_file=gl_obj.source_file,
                        diff_html=diff_html,
                    )
                )
                if is_match:
                    summary.identical += 1
                else:
                    summary.different += 1
            elif gl_obj:
                type_results.append(
                    ObjectCompareResult(
                        object_key=key,
                        object_type=object_type,
                        schema=gl_obj.schema,
                        name=gl_obj.name,
                        parent=gl_obj.parent,
                        status="only_gitlab",
                        gitlab_ddl=gl_obj.ddl,
                        db_ddl="",
                        gitlab_line=gl_obj.start_line,
                        source_file=gl_obj.source_file,
                        diff_html=side_by_side_diff_html(gl_obj.ddl, ""),
                    )
                )
                summary.only_gitlab += 1
            else:
                schema, name, parent = _parse_key(key, object_type)
                type_results.append(
                    ObjectCompareResult(
                        object_key=key,
                        object_type=object_type,
                        schema=schema,
                        name=name,
                        parent=parent,
                        status="only_db",
                        gitlab_ddl="",
                        db_ddl=db_ddl,
                        gitlab_line=None,
                        source_file="",
                        diff_html=side_by_side_diff_html("", db_ddl),
                    )
                )
                summary.only_db += 1

        result.by_type[object_type] = type_results

    result.summary = summary
    return result


def _parse_key(key: str, object_type: str) -> tuple[str, str, str]:
    parts = key.split("::")
    if len(parts) < 2:
        return "", key, ""
    rest = parts[1]
    if object_type in ("CONSTRAINT", "INDEX") and rest.count(".") >= 2:
        schema, parent, name = rest.split(".", 2)
        return schema, name, parent
    if "." in rest:
        schema, name = rest.split(".", 1)
        return schema, name, ""
    return "", rest, ""


def filter_results(
    results: SchemaCompareResult,
    view: str,
    search: str = "",
) -> SchemaCompareResult:
    search_l = search.strip().lower()
    filtered = SchemaCompareResult(
        missing_files=results.missing_files,
        bundle_path=results.bundle_path,
    )
    summary = CompareSummary()
    for object_type, items in results.by_type.items():
        kept: list[ObjectCompareResult] = []
        for item in items:
            if view == "Differences only" and item.status not in ("different", "only_gitlab", "only_db"):
                continue
            if view == "Missing in DB" and item.status != "only_gitlab":
                continue
            if search_l:
                blob = f"{item.name} {item.parent} {item.schema} {item.object_key}".lower()
                if search_l not in blob:
                    continue
            kept.append(item)
            if item.status == "identical":
                summary.identical += 1
            elif item.status == "different":
                summary.different += 1
            elif item.status == "only_gitlab":
                summary.only_gitlab += 1
            else:
                summary.only_db += 1
        filtered.by_type[object_type] = kept
    filtered.summary = summary
    return filtered


def object_from_db_only_key(object_type: str, key: str, ddl: str) -> DeploymentObject:
    schema, name, parent = _parse_key(key, object_type)
    return DeploymentObject(object_type, schema, name, parent, ddl, "", 0)
