"""Deprecated: use repo-root ``studio_entry.py`` (kept for import compatibility)."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_root_app():
    import importlib.util

    entry = _REPO_ROOT / "studio_entry.py"
    spec = importlib.util.spec_from_file_location("studio_entry", entry)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "app", None)


app = _load_root_app()
