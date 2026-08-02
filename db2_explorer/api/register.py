"""Register the Object Explorer search API endpoint.

Strategy (tried in order):
1. Tornado route injection — works on Streamlit <1.53 where the server is Tornado.
2. Background HTTP server — a tiny daemon-thread server on a separate port,
   works on ALL Streamlit versions regardless of its internal server stack.

The JS client gets the correct URL at render time and uses ``fetch()`` for
in-place results.  If both approaches somehow fail, the client falls back to
a full page reload via ``oe_action=search`` query params.
"""

from __future__ import annotations

import gc
import json
import logging
from typing import TYPE_CHECKING, Any, Literal

from streamlit import config

if TYPE_CHECKING:
    from tornado.web import Application

from db2_explorer.api.search_server import get_search_server_port, start_search_server

_LOGGER = logging.getLogger(__name__)

OE_SEARCH_API_PATH = "/api/oe/search"
RC_TEST_DB2_API_PATH = "/api/rc/test-db2"
RC_TEST_AZURE_API_PATH = "/api/rc/test-azure"
RC_LIST_AZURE_DATABASES_API_PATH = "/api/rc/list-azure-databases"
RC_SAVE_CONNECT_API_PATH = "/api/rc/save-connect"
RC_CREATE_BIND_API_PATH = "/api/rc/create-bind"
RC_RUN_COMPARISON_API_PATH = "/api/rc/run-comparison"
SC_LIST_BRANCHES_API_PATH = "/api/sc/list-branches"
SC_LIST_DB_FOLDERS_API_PATH = "/api/sc/list-db-folders"
SC_LIST_SERVER_FOLDERS_API_PATH = "/api/sc/list-server-folders"
SC_LOAD_DEPLOYMENT_API_PATH = "/api/sc/load-deployment"
SC_TEST_AZURE_API_PATH = "/api/sc/test-azure"
SC_LIST_AZURE_DATABASES_API_PATH = "/api/sc/list-azure-databases"
SC_SAVE_CONNECT_API_PATH = "/api/sc/save-connect"
SC_CREATE_BIND_API_PATH = "/api/sc/create-bind"
SC_RUN_COMPARISON_API_PATH = "/api/sc/run-comparison"
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


def oe_search_api_url() -> str:
    """Return the absolute URL the JS client should ``fetch()`` for search.

    If the Tornado route is registered, returns the same-origin path.
    Otherwise returns the background server URL on its separate port.
    """
    if _OE_ROUTE_REGISTERED:
        base = (config.get_option("server.baseUrlPath") or "").strip("/")
        if base:
            return f"/{base}/api/oe/search"
        return OE_SEARCH_API_PATH

    port = get_search_server_port()
    if port is not None:
        return f"http://localhost:{port}/api/oe/search"

    return OE_SEARCH_API_PATH


def _background_api_url(path: str) -> str:
    """Return the fetch URL for an endpoint served by the background API server."""
    port = get_search_server_port()
    if port is not None:
        return f"http://localhost:{port}{path}"
    return path


def rc_test_db2_api_url() -> str:
    """URL for Row Compare DB2 test-connection POST."""
    return _background_api_url(RC_TEST_DB2_API_PATH)


def rc_test_azure_api_url() -> str:
    """URL for Row Compare Azure test-connection POST."""
    return _background_api_url(RC_TEST_AZURE_API_PATH)


def rc_list_azure_databases_api_url() -> str:
    """URL for Row Compare Azure database list POST."""
    return _background_api_url(RC_LIST_AZURE_DATABASES_API_PATH)


def rc_save_connect_api_url() -> str:
    """URL for Row Compare credential save POST."""
    return _background_api_url(RC_SAVE_CONNECT_API_PATH)


def rc_create_bind_api_url() -> str:
    """URL for Row Compare one-time session bind POST (Edit credentials)."""
    return _background_api_url(RC_CREATE_BIND_API_PATH)


def rc_run_comparison_api_url() -> str:
    """URL for Row Compare run POST."""
    return _background_api_url(RC_RUN_COMPARISON_API_PATH)


def sc_list_branches_api_url() -> str:
    return _background_api_url(SC_LIST_BRANCHES_API_PATH)


def sc_list_db_folders_api_url() -> str:
    return _background_api_url(SC_LIST_DB_FOLDERS_API_PATH)


def sc_list_server_folders_api_url() -> str:
    return _background_api_url(SC_LIST_SERVER_FOLDERS_API_PATH)


def sc_load_deployment_api_url() -> str:
    return _background_api_url(SC_LOAD_DEPLOYMENT_API_PATH)


def sc_test_azure_api_url() -> str:
    return _background_api_url(SC_TEST_AZURE_API_PATH)


def sc_list_azure_databases_api_url() -> str:
    return _background_api_url(SC_LIST_AZURE_DATABASES_API_PATH)


def sc_save_connect_api_url() -> str:
    return _background_api_url(SC_SAVE_CONNECT_API_PATH)


def sc_create_bind_api_url() -> str:
    return _background_api_url(SC_CREATE_BIND_API_PATH)


def sc_run_comparison_api_url() -> str:
    return _background_api_url(SC_RUN_COMPARISON_API_PATH)


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
    _LOGGER.info("Registered Object Explorer search API on Tornado at %s", OE_SEARCH_API_PATH)
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


def _try_tornado_registration() -> bool:
    """Attempt Tornado-based route registration (best for older Streamlit)."""
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


def _get_streamlit_port() -> int:
    try:
        return int(config.get_option("server.port") or 8501)
    except Exception:
        return 8501


def ensure_oe_search_api() -> bool:
    """Ensure API endpoints are reachable.

    OE search may use a Tornado same-origin route; Row Compare test/list APIs always
    use the background server, so that server is started whenever possible.
    """
    _try_tornado_registration()
    port = start_search_server(_get_streamlit_port())
    return _OE_ROUTE_REGISTERED or port is not None
