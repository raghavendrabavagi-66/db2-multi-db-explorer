"""Register custom HTTP routes on the Streamlit/Tornado server.

Best-effort: if Tornado is available and Streamlit uses the Tornado server,
we mount POST /api/oe/search.  If not, the JS client falls back to a full
page reload via ``oe_action=search`` query params (handled server-side in
``pages/1_Object_Explorer.py``).
"""

from __future__ import annotations

import gc
import json
import logging
from typing import TYPE_CHECKING, Any, Literal

from streamlit import config

if TYPE_CHECKING:
    from tornado.web import Application

_LOGGER = logging.getLogger(__name__)

OE_SEARCH_API_PATH = "/api/oe/search"
_CREATE_APP_PATCHED = False
_OE_ROUTE_REGISTERED = False
_SEARCH_HANDLER_CLS: type[Any] | None = None


def _tornado_available() -> bool:
    try:
        import tornado  # noqa: F401
    except ImportError:
        return False
    return True


def _make_url_path_regex(
    *path: str,
    trailing_slash: Literal["optional", "required", "prohibited"] = "optional",
) -> str:
    try:
        from streamlit.web.server.server_util import make_url_path_regex

        return make_url_path_regex(*path, trailing_slash=trailing_slash)
    except ImportError:
        filtered_paths = [segment.strip("/") for segment in path if segment]
        if trailing_slash == "optional":
            path_format = r"^/%s/?$"
        elif trailing_slash == "required":
            path_format = r"^/%s/$"
        else:
            path_format = r"^/%s$"
        return path_format % "/".join(filtered_paths)


def oe_search_api_path() -> str:
    """Browser fetch path respecting Streamlit ``server.baseUrlPath``."""
    base = (config.get_option("server.baseUrlPath") or "").strip("/")
    if base:
        return f"/{base}/api/oe/search"
    return OE_SEARCH_API_PATH


def _search_handler_cls() -> type[Any]:
    """Build the Tornado RequestHandler lazily."""
    global _SEARCH_HANDLER_CLS
    if _SEARCH_HANDLER_CLS is not None:
        return _SEARCH_HANDLER_CLS

    from tornado.web import RequestHandler

    from db2_explorer.api.oe_search_service import execute_search_json

    class _OESearchHandler(RequestHandler):

        check_xsrf_cookie = lambda self: None  # noqa: E731

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

            try:
                payload = execute_search_json(body)
            except Exception as exc:
                _LOGGER.exception("Object Explorer search API failed")
                self.set_status(500)
                self.set_header("Content-Type", "application/json")
                self.write(json.dumps({"ok": False, "error": str(exc)}))
                return

            self.set_header("Content-Type", "application/json")
            self.set_status(200 if payload.get("ok") else 400)
            self.write(json.dumps(payload))

    _SEARCH_HANDLER_CLS = _OESearchHandler
    return _SEARCH_HANDLER_CLS


def _route_pattern() -> str:
    base = config.get_option("server.baseUrlPath") or ""
    return _make_url_path_regex(base, "api/oe/search")


def _wildcard_router(app: Application):
    return app.wildcard_router


def _route_is_registered(app: Application, pattern: str) -> bool:
    for rule in _wildcard_router(app).rules:
        matcher = getattr(rule, "matcher", None)
        regex = getattr(matcher, "regex", None)
        if regex is not None and getattr(regex, "pattern", None) == pattern:
            return True
    return False


def _register_route_on_app(app: Application) -> bool:
    from tornado.routing import PathMatches, Rule

    pattern = _route_pattern()
    router = _wildcard_router(app)
    if _route_is_registered(app, pattern):
        return True

    handler_cls = _search_handler_cls()
    rule = router.process_rule(Rule(PathMatches(pattern), handler_cls))
    router.rules.insert(0, rule)
    _LOGGER.info("Registered Object Explorer search API at %s", oe_search_api_path())
    return True


def _find_live_app() -> Application | None:
    from tornado.web import Application as TornadoApplication

    try:
        from tornado.httpserver import HTTPServer
    except ImportError:
        return None

    for obj in gc.get_objects():
        if type(obj) is HTTPServer:
            callback = obj.request_callback
            if type(callback) is TornadoApplication:
                return callback

    apps = [obj for obj in gc.get_objects() if type(obj) is TornadoApplication]
    if not apps:
        return None
    if len(apps) == 1:
        return apps[0]
    return max(apps, key=lambda app: len(getattr(_wildcard_router(app), "rules", [])))


def _try_patch_create_app() -> bool:
    """Monkey-patch Server._create_app to insert our route (Tornado-based Streamlit only)."""
    global _CREATE_APP_PATCHED
    if _CREATE_APP_PATCHED:
        return _OE_ROUTE_REGISTERED

    _CREATE_APP_PATCHED = True

    try:
        from streamlit.web.server import server as st_server
    except ImportError:
        return False

    if not hasattr(st_server.Server, "_create_app"):
        return False

    original = st_server.Server._create_app

    def _patched(self):  # noqa: ANN001
        app = original(self)
        _register_route_on_app(app)
        global _OE_ROUTE_REGISTERED
        _OE_ROUTE_REGISTERED = True
        return app

    st_server.Server._create_app = _patched
    return True


def ensure_oe_search_api() -> bool:
    """Best-effort: mount POST /api/oe/search on the Tornado server.

    Returns True if the route is registered.  Returns False silently when
    Tornado is unavailable (e.g. Streamlit 1.53+ ASGI) — the JS client
    will use the page-reload fallback automatically.
    """
    if not _tornado_available():
        return False

    global _OE_ROUTE_REGISTERED
    if _OE_ROUTE_REGISTERED:
        return True

    try:
        _try_patch_create_app()
    except Exception:
        pass

    if _OE_ROUTE_REGISTERED:
        return True

    try:
        app = _find_live_app()
    except Exception:
        return False

    if app is None:
        return False

    if _register_route_on_app(app):
        _OE_ROUTE_REGISTERED = True
        return True
    return False
