"""Object Explorer API routes (placeholder for Streamlit migration)."""

from __future__ import annotations

from fastapi import APIRouter

from db2_explorer.api.oe_search_service import execute_search_json

router = APIRouter(prefix="/oe", tags=["object-explorer"])


@router.post("/search")
def search(body: dict) -> dict:
    payload = execute_search_json(body)
    if not payload.get("ok"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=payload.get("error") or "Search failed.")
    return payload
