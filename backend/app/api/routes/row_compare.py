"""Row Compare API routes."""

from __future__ import annotations

from typing import Any, Optional, Union

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db2_explorer.api.rc_connect_service import (
    get_connect_json,
    list_azure_databases_json,
    save_connect_json,
    test_azure_json,
    test_db2_json,
)
from db2_explorer.api.rc_run_service import run_comparison_json

router = APIRouter(prefix="/rc", tags=["row-compare"])


class JsonBody(BaseModel):
    model_config = {"extra": "allow"}


class SaveConnectBody(BaseModel):
    rc_sid: str
    database: str
    host: str
    port: Union[int, str] = 50000
    username: str
    password: str
    server: str
    az_database: str
    auth_method: str = "entra"
    trust_server_certificate: bool = False


class RunComparisonBody(BaseModel):
    rc_sid: str
    target_table_mode: str = "original"
    db2_schema: Optional[str] = None
    azure_schema: Optional[str] = None


def _respond(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("ok"):
        raise HTTPException(status_code=400, detail=payload.get("error") or "Request failed.")
    return payload


@router.get("/connect/{rc_sid}")
def get_connect(rc_sid: str) -> dict[str, Any]:
    return get_connect_json(rc_sid)


@router.post("/test-db2")
def test_db2(body: dict[str, Any]) -> dict[str, Any]:
    return _respond(test_db2_json(body))


@router.post("/test-azure")
def test_azure(body: dict[str, Any]) -> dict[str, Any]:
    return _respond(test_azure_json(body))


@router.post("/list-azure-databases")
def list_azure_databases(body: dict[str, Any]) -> dict[str, Any]:
    return _respond(list_azure_databases_json(body))


@router.post("/save-connect")
def save_connect(body: SaveConnectBody) -> dict[str, Any]:
    return _respond(save_connect_json(body.model_dump()))


@router.post("/run-comparison")
def run_comparison(body: RunComparisonBody) -> dict[str, Any]:
    return _respond(run_comparison_json(body.model_dump(exclude_none=True)))
