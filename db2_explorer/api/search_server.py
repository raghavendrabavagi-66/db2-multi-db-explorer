"""Standalone background HTTP server for iframe AJAX APIs (OE search, RC tests).

Started as a daemon thread so endpoints work regardless of Streamlit's web stack.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable
from urllib.parse import urlparse

from db2_explorer.api.oe_search_service import execute_search_json
from db2_explorer.api.rc_connect_service import (
    create_bind_json,
    list_azure_databases_json,
    save_connect_json,
    test_azure_json,
    test_db2_json,
)
from db2_explorer.api.rc_run_service import run_comparison_json

_LOGGER = logging.getLogger(__name__)

_server: HTTPServer | None = None
_port: int | None = None
_streamlit_port: int = 8501
_lock = threading.Lock()

_POST_ROUTES: dict[str, Callable[[dict], dict]] = {
    "/api/oe/search": execute_search_json,
    "/api/rc/test-db2": test_db2_json,
    "/api/rc/test-azure": test_azure_json,
    "/api/rc/list-azure-databases": list_azure_databases_json,
    "/api/rc/save-connect": save_connect_json,
    "/api/rc/create-bind": create_bind_json,
    "/api/rc/run-comparison": run_comparison_json,
}


def _allowed_origins() -> set[str]:
    port = _streamlit_port
    return {
        f"http://localhost:{port}",
        f"http://127.0.0.1:{port}",
        f"https://localhost:{port}",
        f"https://127.0.0.1:{port}",
    }


def _origin_allowed(origin: str | None, referer: str | None) -> str | None:
    """Return the Access-Control-Allow-Origin value to echo, or None to deny."""
    allowed = _allowed_origins()
    if origin in allowed:
        return origin
    if origin == "null":
        ref = referer or ""
        for candidate in allowed:
            host = urlparse(candidate).netloc
            if host and host in ref:
                return "null"
    if not origin and referer:
        for candidate in allowed:
            if candidate.rstrip("/") in referer or referer.startswith(candidate):
                return candidate
    return None


class _ApiHandler(BaseHTTPRequestHandler):

    def _resolve_cors_origin(self) -> str | None:
        return _origin_allowed(
            self.headers.get("Origin"),
            self.headers.get("Referer"),
        )

    def _send_cors_headers(self) -> None:
        origin = self._resolve_cors_origin()
        if origin is None:
            return
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Vary", "Origin")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        if self._resolve_cors_origin() is None:
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self._resolve_cors_origin() is None:
            self.send_response(403)
            self.end_headers()
            return

        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        handler = _POST_ROUTES.get(path)
        if handler is None:
            self._send_json({"ok": False, "error": "Not found."}, 404)
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"

        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json({"ok": False, "error": "Invalid JSON body."}, 400)
            return

        if not isinstance(body, dict):
            self._send_json({"ok": False, "error": "Expected JSON object."}, 400)
            return

        try:
            payload = handler(body)
        except Exception as exc:
            _LOGGER.exception("API handler failed for %s", path)
            self._send_json({"ok": False, "error": str(exc)}, 500)
            return

        status = 200 if payload.get("ok") else 400
        self._send_json(payload, status)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        _LOGGER.debug("ApiServer: %s", format % args)


def _find_free_port(preferred: int) -> int:
    for port in [preferred, preferred + 1, preferred + 2]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_search_server(streamlit_port: int = 8501) -> int:
    """Start the background API server and return its port."""
    global _server, _port, _streamlit_port

    with _lock:
        _streamlit_port = streamlit_port
        if _server is not None and _port is not None:
            return _port

        preferred = streamlit_port + 1000
        port = _find_free_port(preferred)

        server = HTTPServer(("127.0.0.1", port), _ApiHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        _server = server
        _port = port
        _LOGGER.info(
            "Background API server started on http://127.0.0.1:%d (Streamlit :%d)",
            port,
            streamlit_port,
        )
        return port


def get_search_server_port() -> int | None:
    """Return the port if the background server is running, else None."""
    return _port


def api_url(path: str) -> str:
    """Absolute URL for a background API path (e.g. /api/rc/test-db2)."""
    port = get_search_server_port()
    if port is not None:
        return f"http://localhost:{port}{path}"
    return path
