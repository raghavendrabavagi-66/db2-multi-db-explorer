"""API router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.routes import object_explorer, row_compare

api_router = APIRouter()
api_router.include_router(row_compare.router)
api_router.include_router(object_explorer.router)


@api_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
