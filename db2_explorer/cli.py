"""Streamlit CLI wrapper — pre-registers OE search API on Tornado-based Streamlit."""

from __future__ import annotations

from db2_explorer.api.register import ensure_oe_search_api


def main() -> None:
    ensure_oe_search_api()
    from streamlit.web.cli import main as streamlit_main

    streamlit_main()


if __name__ == "__main__":
    main()
