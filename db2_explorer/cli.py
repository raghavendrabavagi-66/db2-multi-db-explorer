"""Streamlit CLI wrapper that registers Object Explorer API routes at startup."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from db2_explorer.api.register import install_oe_search_api

_ASGI_SEARCH_ENV = "DB2_MIGRATION_STUDIO_ASGI_SEARCH"


def _rewrite_argv_for_starlette_entry() -> bool:
    """On Streamlit 1.53+, run the ASGI entry that declares /api/oe/search."""
    if len(sys.argv) < 3 or sys.argv[1] != "run":
        return False

    target = Path(sys.argv[2]).name
    if target not in {"app.py", "app"}:
        return False

    try:
        from streamlit.web.server import server as st_server
    except ImportError:
        return False

    if hasattr(st_server.Server, "_create_app"):
        return False

    try:
        from db2_explorer import studio_app
    except ImportError:
        return False

    if studio_app.app is None:
        return False

    entry = Path(studio_app.__file__).resolve()
    sys.argv[2] = str(entry)
    os.environ[_ASGI_SEARCH_ENV] = "1"
    return True


def main() -> None:
    install_oe_search_api()
    _rewrite_argv_for_starlette_entry()
    from streamlit.web.cli import main as streamlit_main

    streamlit_main()


if __name__ == "__main__":
    main()
