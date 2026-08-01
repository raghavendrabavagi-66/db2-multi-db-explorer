"""Register custom HTTP routes on the Streamlit/Tornado server."""

from __future__ import annotations

import gc
import json

import streamlit as st

OE_SEARCH_API_PATH = "/api/oe/search"


_OE_ROUTE_REGISTERED = False


@st.cache_resource
def ensure_oe_search_api() -> bool:
    """Mount POST /api/oe/search once for iframe AJAX search."""
    global _OE_ROUTE_REGISTERED
    if _OE_ROUTE_REGISTERED:
        return True
    try:
        from tornado.routing import Rule, PathMatches
        from tornado.web import Application, RequestHandler

        from db2_explorer.api.oe_search_service import execute_search_json
    except ImportError:
        return False

    class OESearchHandler(RequestHandler):
        def set_default_headers(self) -> None:
            self.set_header("Access-Control-Allow-Origin", "*")
            self.set_header("Access-Control-Allow-Headers", "Content-Type")
            self.set_header("Access-Control-Allow-Methods", "POST, OPTIONS")

        def options(self) -> None:
            self.set_status(204)
            self.finish()

        def post(self) -> None:
            try:
                body = json.loads(self.request.body or b"{}")
            except json.JSONDecodeError:
                self.set_status(400)
                self.set_header("Content-Type", "application/json")
                self.write(json.dumps({"ok": False, "error": "Invalid JSON body."}))
                return

            if not isinstance(body, dict):
                self.set_status(400)
                self.set_header("Content-Type", "application/json")
                self.write(json.dumps({"ok": False, "error": "Expected JSON object."}))
                return

            payload = execute_search_json(body)
            self.set_header("Content-Type", "application/json")
            self.set_status(200 if payload.get("ok") else 400)
            self.write(json.dumps(payload))

    try:
        tornado_app = next(
            o for o in gc.get_referrers(Application) if o.__class__ is Application
        )
    except StopIteration:
        return False

    tornado_app.wildcard_router.rules.insert(
        0,
        Rule(PathMatches(OE_SEARCH_API_PATH), OESearchHandler),
    )
    _OE_ROUTE_REGISTERED = True
    return True
