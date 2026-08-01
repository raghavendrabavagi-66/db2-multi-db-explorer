"""Streamlit 1.53+ ASGI entry — must live next to app.py and pages/."""

from __future__ import annotations

import json
import logging

from pathlib import Path

from db2_explorer.api.oe_search_service import execute_search_json

_LOGGER = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent
_MAIN_SCRIPT = str(_ROOT / "app.py")

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
}


def _try_build_starlette_app():
    try:
        from streamlit.starlette import App
        from starlette.requests import Request
        from starlette.responses import JSONResponse, Response
        from starlette.routing import Route
    except ImportError:
        return None

    async def oe_search(request: Request) -> Response:
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=_CORS_HEADERS)

        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse(
                {"ok": False, "error": "Invalid JSON body."},
                status_code=400,
                headers=_CORS_HEADERS,
            )

        if not isinstance(body, dict):
            return JSONResponse(
                {"ok": False, "error": "Expected JSON object."},
                status_code=400,
                headers=_CORS_HEADERS,
            )

        try:
            payload = execute_search_json(body)
        except Exception as exc:  # pragma: no cover - DB/driver failures
            _LOGGER.exception("Object Explorer search API failed")
            return JSONResponse(
                {"ok": False, "error": str(exc)},
                status_code=500,
                headers=_CORS_HEADERS,
            )

        status = 200 if payload.get("ok") else 400
        return JSONResponse(payload, status_code=status, headers=_CORS_HEADERS)

    return App(
        _MAIN_SCRIPT,
        routes=[Route("/api/oe/search", oe_search, methods=["POST", "OPTIONS"])],
    )


app = _try_build_starlette_app()
