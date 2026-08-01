"""Streamlit CLI wrapper that registers Object Explorer API routes at startup."""

from __future__ import annotations

from db2_explorer.api.register import install_oe_search_api


def main() -> None:
    install_oe_search_api()
    from streamlit.web.cli import main as streamlit_main

    streamlit_main()


if __name__ == "__main__":
    main()
