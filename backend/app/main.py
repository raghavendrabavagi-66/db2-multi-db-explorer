"""FastAPI entrypoint for DB2 Migration Studio."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.router import api_router
from backend.app.core.config import API_PREFIX, CORS_ORIGINS

app = FastAPI(
    title="DB2 Migration Studio API",
    version="2.0.0",
    description="REST API for Row Compare, Object Explorer, and Schema Compare.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=API_PREFIX)

_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        """Serve React SPA — API paths are registered above this catch-all."""
        if full_path.startswith("api/"):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Not found")
        index = _FRONTEND_DIST / "index.html"
        if full_path and (_FRONTEND_DIST / full_path).is_file():
            return FileResponse(_FRONTEND_DIST / full_path)
        return FileResponse(index)
