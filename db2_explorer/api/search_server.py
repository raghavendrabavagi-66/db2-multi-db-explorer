"""Standalone background HTTP server for the Object Explorer search API.

Started as a daemon thread so the search endpoint works regardless of
which web server Streamlit uses internally (Tornado or Starlette).
"""

from __future__ import annotations

import json
import logging
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from db2_explorer.api.oe_search_service import execute_search_json

_LOGGER = logging.getLogger(__name__)

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
}

_server: HTTPServer | None = None
_port: int | None = None
_lock = threading.Lock()


class _SearchHandler(BaseHTTPRequestHandler):

    def _send_cors_headers(self) -> None:
        for key, val in _CORS_HEADERS.items():
            self.send_header(key, val)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/api/oe/search":
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
            payload = execute_search_json(body)
        except Exception as exc:
            _LOGGER.exception("Object Explorer search API failed")
            self._send_json({"ok": False, "error": str(exc)}, 500)
            return

        status = 200 if payload.get("ok") else 400
        self._send_json(payload, status)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        _LOGGER.debug("SearchServer: %s", format % args)


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
    """Start the background search server and return its port.

    Safe to call multiple times — only the first call starts the server.
    """
    global _server, _port

    with _lock:
        if _server is not None and _port is not None:
            return _port

        preferred = streamlit_port + 1000
        port = _find_free_port(preferred)

        server = HTTPServer(("127.0.0.1", port), _SearchHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        _server = server
        _port = port
        _LOGGER.info(
            "Object Explorer search API server started on http://127.0.0.1:%d/api/oe/search",
            port,
        )
        return port


def get_search_server_port() -> int | None:
    """Return the port if the background server is running, else None."""
    return _port
