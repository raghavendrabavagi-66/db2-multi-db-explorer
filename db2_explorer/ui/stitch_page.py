"""Render stitch_exports index.html files as full self-contained pages."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from db2_explorer.clients.db2 import DBResult
from db2_explorer.data.queries import MATCH_ORDER, OBJECT_TYPES
from db2_explorer.api.register import oe_search_api_url
from db2_explorer.ui.fleet_panel import OE_CLEAR_QUERY_PARAM
from db2_explorer.ui.oe_results import (
    empty_results_row_html,
    results_stats,
    results_tbody_rows,
)
from db2_explorer.ui.stitch_shell import (
    OBJECT_EXPLORER_URL,
    _read_html,
    _wrap_home_cards,
    inject_shell_component,
    shell_iframe_css,
)

_FULL_HEIGHT_SCRIPT = """
<script>
(function () {
  function sync() {
    var h = Math.max(document.documentElement.scrollHeight, window.innerHeight);
    window.parent.postMessage({ type: "streamlit:setFrameHeight", height: h }, "*");
  }
  sync();
  window.addEventListener("load", sync);
  window.addEventListener("resize", sync);
})();
</script>
"""

def render_home_page() -> None:
    """Full stitch home in an iframe; card links in index.html use ?go= for st.switch_page."""
    inject_shell_component(tailwind_config_source="home")
    doc = _wrap_home_cards(_read_html("home"))
    doc = doc.replace("</body>", _FULL_HEIGHT_SCRIPT + "</body>")
    st.markdown(f"<style>{shell_iframe_css()}</style>", unsafe_allow_html=True)
    components.html(doc, height=900, scrolling=False)


@dataclass
class ObjectExplorerView:
    username: str = ""
    password: str = ""
    include_system: bool = False
    max_workers: int = 8
    object_type: str = "Table"
    operator: str = "Begins with"
    filter_text: str = ""
    fleet_rows: list[tuple[str, str, int]] | None = None
    results: list[DBResult] | None = None
    last_meta: dict[str, Any] | None = None
    show_matches_only: bool = False

    @property
    def db_count(self) -> int:
        return len(self.fleet_rows or [])


def _fleet_row_html(db: str, host: str, port: int | str) -> str:
    return (
        '<tr class="hover:bg-surface-container-low group" data-fleet-row>'
        f'<td class="px-md py-2"><input class="oe-fleet-db w-full border-none bg-transparent '
        f'font-code-sm p-0 focus:ring-0 text-sm" type="text" value="{html.escape(str(db))}"></td>'
        f'<td class="px-md py-2"><input class="oe-fleet-host w-full border-none bg-transparent '
        f'font-code-sm p-0 focus:ring-0 text-sm" type="text" value="{html.escape(str(host))}"></td>'
        f'<td class="px-md py-2"><input class="oe-fleet-port w-full border-none bg-transparent '
        f'font-code-sm p-0 focus:ring-0 text-sm" type="text" value="{html.escape(str(port))}"></td>'
        f'<td class="px-2">'
        f'<button type="button" title="Remove database" aria-label="Remove database" '
        f'class="oe-fleet-delete material-symbols-outlined text-outline text-sm '
        f'opacity-0 group-hover:opacity-100 hover:text-error cursor-pointer bg-transparent border-0 p-0">'
        f"delete</button></td>"
        f"</tr>"
    )


def _fleet_empty_row_html() -> str:
    return (
        '<tr id="oe-fleet-empty">'
        '<td colspan="4" class="px-md py-6 text-center text-secondary text-sm">'
        "No databases configured. Click <strong>Add Row</strong> or paste connections below."
        "</td></tr>"
    )


def _fleet_tbody_rows(rows: list[tuple[str, str, int]]) -> str:
    if not rows:
        return _fleet_empty_row_html()
    return "\n".join(_fleet_row_html(db, host, port) for db, host, port in rows)


def _results_tbody_rows(results: list[DBResult], *, matches_only: bool) -> str:
    return results_tbody_rows(results, matches_only=matches_only)


def _empty_results_row_html() -> str:
    return empty_results_row_html()


def _replace_first_tbody(source: str, inner: str) -> str:
    return re.sub(
        r'(<tbody[^>]*class="divide-y divide-outline-variant"[^>]*>)(.*?)(</tbody>)',
        rf"\1{inner}\3",
        source,
        count=1,
        flags=re.DOTALL,
    )


def _replace_results_tbody(source: str, inner: str) -> str:
    parts = list(
        re.finditer(
            r'(<tbody[^>]*class="divide-y divide-outline-variant"[^>]*>)(.*?)(</tbody>)',
            source,
            flags=re.DOTALL,
        )
    )
    if len(parts) < 2:
        return source
    m = parts[1]
    return source[: m.start()] + m.group(1) + inner + m.group(3) + source[m.end() :]


def _results_stats(view: ObjectExplorerView) -> dict[str, Any]:
    stats = results_stats(
        view.results,
        object_type=view.object_type,
        operator=view.operator,
        filter_text=view.filter_text,
        last_meta=view.last_meta,
    )
    if view.results:
        stats["connected_label"] = f"Connected: {stats['reachable']} database(s)"
    else:
        stats["connected_label"] = "Connected: —"
    return stats


def _wire_results_panel(doc: str, view: ObjectExplorerView) -> str:
    stats = _results_stats(view)

    doc = re.sub(
        r'<span class="text-xs font-code-md text-on-surface-variant italic">[^<]*</span>',
        (
            f'<span id="oe-filter-line" class="text-xs font-code-md text-on-surface-variant italic">'
            f'{html.escape(stats["filter_line"])}</span>'
        ),
        doc,
        count=1,
    )
    doc = re.sub(
        r'(<span class="text-\[10px\] font-label-caps text-secondary block">SCANNED</span>\s*'
        r'<span class="text-xl font-bold font-display-lg text-on-surface">)[^<]+(</span>)',
        lambda m: f'{m.group(1)}<span id="oe-stat-scanned">{stats["scanned"]}</span>{m.group(2)}',
        doc,
        count=1,
        flags=re.DOTALL,
    )
    doc = re.sub(
        r'(<span class="text-\[10px\] font-label-caps text-secondary block">REACHABLE</span>\s*'
        r'<span class="text-xl font-bold font-display-lg text-emerald-600">)[^<]+(</span>)',
        lambda m: f'{m.group(1)}<span id="oe-stat-reachable">{stats["reachable"]}</span>{m.group(2)}',
        doc,
        count=1,
        flags=re.DOTALL,
    )
    doc = re.sub(
        r'(<span class="text-\[10px\] font-label-caps text-secondary block">FAILED</span>\s*'
        r'<span class="text-xl font-bold font-display-lg text-error">)[^<]+(</span>)',
        lambda m: f'{m.group(1)}<span id="oe-stat-failed">{stats["failed"]}</span>{m.group(2)}',
        doc,
        count=1,
        flags=re.DOTALL,
    )
    doc = re.sub(
        r'(<span class="text-\[10px\] font-label-caps text-secondary block">MATCHED DBs</span>\s*'
        r'<span class="text-xl font-bold font-display-lg text-primary">)[^<]+(</span>)',
        lambda m: f'{m.group(1)}<span id="oe-stat-matched-dbs">{stats["matched_dbs"]}</span>{m.group(2)}',
        doc,
        count=1,
        flags=re.DOTALL,
    )
    doc = re.sub(
        r'(<span class="text-\[10px\] font-label-caps text-secondary block">TOTAL OBJECTS</span>\s*'
        r'<span class="text-xl font-bold font-display-lg text-on-surface">)[^<]+(</span>)',
        lambda m: f'{m.group(1)}<span id="oe-stat-total-objects">{stats["total_objects"]}</span>{m.group(2)}',
        doc,
        count=1,
        flags=re.DOTALL,
    )

    scan_label = (
        f"Scan Time: {stats['scan_time_s']:.2f}s"
        if stats["scan_time_s"] is not None
        else "Scan Time: —"
    )
    doc = re.sub(
        r"<span>Scan Time: [^<]+</span>",
        f'<span id="oe-scan-time">{scan_label}</span>',
        doc,
        count=1,
    )
    doc = re.sub(
        r"(<span class=\"material-symbols-outlined text-xs\">cloud_done</span>\s*)[^<]+",
        lambda m: f'{m.group(1)}<span id="oe-status-line">{html.escape(stats["status_line"])}</span>',
        doc,
        count=1,
    )
    connected_label = stats.get("connected_label", "Connected: —")
    doc = re.sub(
        r'(<span class="w-1\.5 h-1\.5 rounded-full bg-emerald-500"></span>\s*)Connected: [^<]+',
        lambda m: f'{m.group(1)}<span id="oe-connected-line">{html.escape(connected_label)}</span>',
        doc,
        count=1,
    )

    rows = view.results or []
    doc = _replace_results_tbody(
        doc,
        _results_tbody_rows(rows, matches_only=view.show_matches_only),
    )
    doc = re.sub(
        r'(<table id="oe-results-table"[^>]*>.*?<tbody)( class="divide-y divide-outline-variant")',
        r'\1 id="oe-results-tbody"\2',
        doc,
        count=1,
        flags=re.DOTALL,
    )
    return doc


_OE_MICRO_SCRIPT = re.compile(
    r"<script>\s*// Micro-interaction for UI feel.*?</script>",
    re.DOTALL,
)


def _oe_bridge_script(view: ObjectExplorerView) -> str:
    fleet_row_template = _fleet_row_html("", "", 50000)
    fleet_empty_template = _fleet_empty_row_html()
    empty_results_html = _empty_results_row_html()
    oe_page = OBJECT_EXPLORER_URL
    home_clear_url = f"/?{OE_CLEAR_QUERY_PARAM}=1"
    search_api_url = oe_search_api_url()
    return f"""
<script>
(function () {{
  const MATCH_MODES = {json.dumps(MATCH_ORDER)};
  const OE_PAGE_FALLBACK = {json.dumps(oe_page)};
  const HOME_CLEAR_URL = {json.dumps(home_clear_url)};
  const FLEET_STORAGE_KEY = "db2_migration_studio_oe_fleet";
  const FLEET_HYDRATED_KEY = "db2_migration_studio_oe_fleet_hydrated";
  const EMPTY_RESULTS_HTML = {json.dumps(empty_results_html)};
  const OE_SEARCH_API_URL = {json.dumps(search_api_url)};

  function searchApiUrl() {{
    if (OE_SEARCH_API_URL.startsWith("http")) return OE_SEARCH_API_URL;
    try {{
      const origin = window.top.location.origin;
      if (origin && origin !== "null") return origin + OE_SEARCH_API_URL;
    }} catch (err) {{
      /* cross-frame access blocked */
    }}
    return OE_SEARCH_API_URL;
  }}

  let savedFleetJson = "[]";
  let lastSearchResponse = null;
  let searchInFlight = false;

  function readFleetStorage() {{
    try {{
      const raw = localStorage.getItem(FLEET_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    }} catch (err) {{
      return null;
    }}
  }}

  function writeFleetStorage(rows) {{
    localStorage.setItem(FLEET_STORAGE_KEY, JSON.stringify(rows));
    sessionStorage.setItem(FLEET_HYDRATED_KEY, "1");
  }}

  function clearFleetStorage() {{
    localStorage.removeItem(FLEET_STORAGE_KEY);
    sessionStorage.removeItem(FLEET_HYDRATED_KEY);
  }}

  function maybeHydrateFromStorage() {{
    if (sessionStorage.getItem(FLEET_HYDRATED_KEY) === "1") return;
    const qs = new URLSearchParams(window.location.search);
    if (qs.get("oe_action")) return;
    const rows = readFleetStorage();
    if (!Array.isArray(rows) || rows.length === 0) return;
    sessionStorage.setItem(FLEET_HYDRATED_KEY, "1");
    const params = new URLSearchParams();
    params.set("oe_action", "hydrate");
    params.set("fleet_json", JSON.stringify(rows));
    oeNavigate(params);
  }}

  function oePagePath() {{
    try {{
      const topPath = window.top.location.pathname || "";
      if (topPath.indexOf("Object_Explorer") >= 0) return topPath;
      const parentPath = window.parent.location.pathname || "";
      if (parentPath.indexOf("Object_Explorer") >= 0) return parentPath;
    }} catch (err) {{
      /* cross-frame access blocked */
    }}
    return OE_PAGE_FALLBACK;
  }}

  function oeNavigate(params) {{
    const url = oePagePath() + "?" + params.toString();
    window.parent.postMessage({{ type: "stitch-oe-nav", url: url }}, "*");
    if (window.top && window.top !== window) {{
      window.top.postMessage({{ type: "stitch-oe-nav", url: url }}, "*");
    }}
    try {{
      window.top.location.href = url;
    }} catch (err) {{
      /* parent bridge handles navigation */
    }}
  }}

  function navigateHomeClear() {{
    clearFleetStorage();
    sessionStorage.removeItem(FLEET_HYDRATED_KEY);
    window.parent.postMessage({{ type: "stitch-oe-nav", url: HOME_CLEAR_URL }}, "*");
    if (window.top && window.top !== window) {{
      window.top.postMessage({{ type: "stitch-oe-nav", url: HOME_CLEAR_URL }}, "*");
    }}
    try {{
      window.top.location.href = HOME_CLEAR_URL;
    }} catch (err) {{
      /* parent bridge handles navigation */
    }}
  }}

  function wireHomeNav() {{
    const targets = document.querySelectorAll("#oe-home-back, .oe-home-link");
    targets.forEach(function (link) {{
      link.addEventListener("click", function (event) {{
        event.preventDefault();
        navigateHomeClear();
      }});
    }});
  }}

  function collectFleetRows() {{
    const rows = [];
    document.querySelectorAll("#oe-fleet-tbody tr[data-fleet-row]").forEach(function (tr) {{
      const db = (tr.querySelector(".oe-fleet-db") || {{ value: "" }}).value.trim();
      const host = (tr.querySelector(".oe-fleet-host") || {{ value: "" }}).value.trim();
      const port = (tr.querySelector(".oe-fleet-port") || {{ value: "50000" }}).value.trim() || "50000";
      if (db && host) rows.push([db, host, port]);
    }});
    return rows;
  }}

  const SAVE_BTN_ACTIVE =
    "px-3 py-1 text-xs font-semibold bg-primary text-white rounded hover:bg-primary/90 transition-colors";
  const SAVE_BTN_SAVED =
    "px-3 py-1 text-xs font-semibold bg-surface-container-high text-secondary rounded cursor-not-allowed";
  const SAVE_BTN_DISABLED =
    "px-3 py-1 text-xs font-semibold bg-primary/40 text-white rounded cursor-not-allowed";

  function fleetSnapshot() {{
    return JSON.stringify(collectFleetRows());
  }}

  function syncSavedSnapshotFromStorage() {{
    const rows = readFleetStorage();
    savedFleetJson = JSON.stringify(Array.isArray(rows) ? rows : []);
  }}

  function hasIncompleteRows() {{
    let incomplete = false;
    document.querySelectorAll("#oe-fleet-tbody tr[data-fleet-row]").forEach(function (tr) {{
      const db = (tr.querySelector(".oe-fleet-db") || {{ value: "" }}).value.trim();
      const host = (tr.querySelector(".oe-fleet-host") || {{ value: "" }}).value.trim();
      if (!db || !host) incomplete = true;
    }});
    return incomplete;
  }}

  function isSavable() {{
    return collectFleetRows().length > 0;
  }}

  function isDirty() {{
    return fleetSnapshot() !== savedFleetJson || hasIncompleteRows();
  }}

  function removeIncompleteFleetRows() {{
    document.querySelectorAll("#oe-fleet-tbody tr[data-fleet-row]").forEach(function (tr) {{
      const db = (tr.querySelector(".oe-fleet-db") || {{ value: "" }}).value.trim();
      const host = (tr.querySelector(".oe-fleet-host") || {{ value: "" }}).value.trim();
      if (!db || !host) tr.remove();
    }});
    ensureFleetEmptyState();
  }}

  function updateSaveButtonState() {{
    const btn = document.getElementById("oe-save-fleet");
    if (!btn) return;
    const dirty = isDirty();
    const savable = isSavable();
    if (!dirty) {{
      btn.disabled = true;
      btn.textContent = "Saved";
      btn.title = "Fleet matches browser storage";
      btn.className = SAVE_BTN_SAVED;
      return;
    }}
    btn.textContent = "Save Fleet";
    if (savable) {{
      btn.disabled = false;
      btn.title = "Save fleet to browser storage";
      btn.className = SAVE_BTN_ACTIVE;
      return;
    }}
    btn.disabled = true;
    btn.title = "Enter database and host on at least one row to save";
    btn.className = SAVE_BTN_DISABLED;
  }}

  function setText(id, text) {{
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }}

  function showToast(message) {{
    let toast = document.getElementById("oe-toast");
    if (!toast) {{
      toast = document.createElement("div");
      toast.id = "oe-toast";
      toast.style.cssText =
        "position:fixed;bottom:2rem;left:50%;transform:translateX(-50%);z-index:9999;" +
        "background:#131b2e;color:#fff;padding:0.5rem 1rem;border-radius:6px;font-size:12px;" +
        "box-shadow:0 4px 12px rgba(0,0,0,0.15);opacity:0;transition:opacity 0.2s ease;";
      document.body.appendChild(toast);
    }}
    toast.textContent = message;
    toast.style.opacity = "1";
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(function () {{
      toast.style.opacity = "0";
    }}, 2500);
  }}

  function updateFleetLabels(count) {{
    const suffix = count === 1 ? "" : "s";
    setText("oe-db-count-subheader", count + " Database" + suffix + " Configured");
    setText("oe-fleet-title", "Database Fleet (" + count + " database" + suffix + ")");
  }}

  function updateFleetLabelsFromDom() {{
    updateFleetLabels(collectFleetRows().length);
  }}

  function clearFleetTable() {{
    const tbody = document.getElementById("oe-fleet-tbody");
    if (!tbody) return;
    tbody.querySelectorAll("tr").forEach(function (tr) {{ tr.remove(); }});
    ensureFleetEmptyState();
    updateFleetLabels(0);
  }}

  function resetResultsPanel() {{
    lastSearchResponse = null;
    setText("oe-filter-line", "No search run yet");
    setText("oe-stat-scanned", "0");
    setText("oe-stat-reachable", "0");
    setText("oe-stat-failed", "0");
    setText("oe-stat-matched-dbs", "0");
    setText("oe-stat-total-objects", "0");
    setText("oe-status-line", "Ready");
    setText("oe-scan-time", "Scan Time: —");
    setText("oe-connected-line", "Connected: —");
    const tbody = document.getElementById("oe-results-tbody");
    if (tbody) tbody.innerHTML = EMPTY_RESULTS_HTML;
    const matchesOnly = document.getElementById("oe-matches-only");
    if (matchesOnly) matchesOnly.checked = false;
  }}

  function resetSearchInputs() {{
    const filter = document.getElementById("oe-filter-text");
    if (filter) filter.value = "";
    const typeSelect = document.getElementById("oe-object-type");
    if (typeSelect) typeSelect.selectedIndex = 0;
    const radios = document.querySelectorAll('input[name="match_mode"]');
    radios.forEach(function (radio, idx) {{
      radio.checked = idx === 0;
    }});
  }}

  function resetAllExceptConnection() {{
    clearFleetStorage();
    savedFleetJson = "[]";
    clearFleetTable();
    resetResultsPanel();
    resetSearchInputs();
    const paste = document.getElementById("oe-paste-area");
    if (paste) paste.value = "";
    updateSaveButtonState();
    showToast("Reset complete — connection settings preserved.");
  }}

  function appendFleetParams(params) {{
    params.set("fleet_json", JSON.stringify(collectFleetRows()));
  }}

  function connectionParams(params) {{
    params.set("username", (document.getElementById("oe-username") || {{ value: "" }}).value || "");
    params.set("password", (document.getElementById("oe-password") || {{ value: "" }}).value || "");
    params.set("include_system", (document.getElementById("oe-include-system") || {{ checked: false }}).checked ? "1" : "0");
    params.set("max_workers", (document.getElementById("oe-max-workers") || {{ value: "8" }}).value || "8");
  }}

  function navigateSearchFallback() {{
    const params = new URLSearchParams();
    params.set("oe_action", "search");
    connectionParams(params);
    params.set("filter_text", (document.getElementById("oe-filter-text") || {{ value: "" }}).value || "");
    const typeSelect = document.getElementById("oe-object-type");
    if (typeSelect) params.set("object_type", typeSelect.options[typeSelect.selectedIndex].text);
    const checked = document.querySelector('input[name="match_mode"]:checked');
    const radios = Array.from(document.querySelectorAll('input[name="match_mode"]'));
    const modeIdx = checked ? radios.indexOf(checked) : 0;
    params.set("operator", MATCH_MODES[modeIdx] || {json.dumps(view.operator)!r});
    appendFleetParams(params);
    oeNavigate(params);
  }}

  function buildSearchBody() {{
    const checked = document.querySelector('input[name="match_mode"]:checked');
    const radios = Array.from(document.querySelectorAll('input[name="match_mode"]'));
    const modeIdx = checked ? radios.indexOf(checked) : 0;
    const typeSelect = document.getElementById("oe-object-type");
    return {{
      username: (document.getElementById("oe-username") || {{ value: "" }}).value || "",
      password: (document.getElementById("oe-password") || {{ value: "" }}).value || "",
      include_system: (document.getElementById("oe-include-system") || {{ checked: false }}).checked,
      max_workers: (document.getElementById("oe-max-workers") || {{ value: "8" }}).value || "8",
      filter_text: (document.getElementById("oe-filter-text") || {{ value: "" }}).value || "",
      object_type: typeSelect ? typeSelect.options[typeSelect.selectedIndex].text : "Table",
      operator: MATCH_MODES[modeIdx] || {json.dumps(view.operator)!r},
      fleet: collectFleetRows(),
    }};
  }}

  function applySearchResults(payload, matchesOnly) {{
    if (!payload || !payload.ok) return;
    const stats = payload.stats || {{}};
    setText("oe-filter-line", stats.filter_line || "No search run yet");
    setText("oe-stat-scanned", String(stats.scanned ?? 0));
    setText("oe-stat-reachable", String(stats.reachable ?? 0));
    setText("oe-stat-failed", String(stats.failed ?? 0));
    setText("oe-stat-matched-dbs", String(stats.matched_dbs ?? 0));
    setText("oe-stat-total-objects", String(stats.total_objects ?? 0));
    setText("oe-status-line", stats.status_line || "Ready");
    setText("oe-scan-time", payload.scan_time_label || "Scan Time: —");
    setText("oe-connected-line", stats.connected_label || "Connected: —");
    const tbody = document.getElementById("oe-results-tbody");
    if (tbody) {{
      const rowsHtml = matchesOnly ? payload.tbody_html_matches : payload.tbody_html_all;
      tbody.innerHTML = rowsHtml || EMPTY_RESULTS_HTML;
    }}
  }}

  function renderMatchesOnlyFromCache() {{
    if (!lastSearchResponse) return;
    const box = document.getElementById("oe-matches-only");
    applySearchResults(lastSearchResponse, !!(box && box.checked));
  }}

  async function runSearch() {{
    if (searchInFlight) return;
    const searchBtn = document.getElementById("oe-search-btn");
    const originalHtml = searchBtn ? searchBtn.innerHTML : "";
    searchInFlight = true;
    if (searchBtn) {{
      searchBtn.disabled = true;
      searchBtn.innerHTML =
        '<span class="material-symbols-outlined animate-spin text-sm">sync</span> Searching...';
    }}
    try {{
      const response = await fetch(searchApiUrl(), {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(buildSearchBody()),
      }});
      const contentType = (response.headers.get("content-type") || "").toLowerCase();
      if (!contentType.includes("application/json")) {{
        showToast("Search API unavailable — reloading with server search.");
        navigateSearchFallback();
        return;
      }}
      let payload = {{ ok: false, error: "Search failed." }};
      try {{
        payload = await response.json();
      }} catch (parseErr) {{
        showToast("Search API unavailable — reloading with server search.");
        navigateSearchFallback();
        return;
      }}
      if (!response.ok || !payload.ok) {{
        showToast(payload.error || ("Search failed (HTTP " + response.status + ")."));
        return;
      }}
      lastSearchResponse = payload;
      const matchesOnly = document.getElementById("oe-matches-only");
      applySearchResults(payload, !!(matchesOnly && matchesOnly.checked));
    }} catch (err) {{
      showToast("Search request failed — reloading with server search.");
      navigateSearchFallback();
    }} finally {{
      searchInFlight = false;
      if (searchBtn) {{
        searchBtn.disabled = false;
        searchBtn.innerHTML = originalHtml || "Search all databases";
      }}
    }}
  }}

  function wireSlider() {{
    const slider = document.getElementById("oe-max-workers");
    if (!slider) return;
    slider.addEventListener("input", function (event) {{
      const label = event.target.parentElement.querySelector(".font-code-md");
      if (label) label.textContent = event.target.value;
    }});
  }}

  function wireFleetActions() {{
    const resetBtn = document.getElementById("oe-reset-fleet");
    if (resetBtn) {{
      resetBtn.addEventListener("click", function (event) {{
        event.preventDefault();
        resetAllExceptConnection();
      }});
    }}

    const saveBtn = document.getElementById("oe-save-fleet");
    if (saveBtn) {{
      saveBtn.addEventListener("click", function (event) {{
        event.preventDefault();
        if (saveBtn.disabled) return;
        removeIncompleteFleetRows();
        const rows = collectFleetRows();
        if (rows.length === 0) return;
        writeFleetStorage(rows);
        savedFleetJson = JSON.stringify(rows);
        updateFleetLabels(rows.length);
        updateSaveButtonState();
        showToast("Saved " + rows.length + " database(s) to browser storage.");
      }});
    }}

    const addRow = document.getElementById("oe-add-row");
    if (addRow) {{
      addRow.addEventListener("click", function (event) {{
        event.preventDefault();
        const tbody = document.getElementById("oe-fleet-tbody");
        if (!tbody) return;
        const emptyRow = document.getElementById("oe-fleet-empty");
        if (emptyRow) emptyRow.remove();
        const template = document.createElement("tbody");
        template.innerHTML = {json.dumps(fleet_row_template)};
        const row = template.firstElementChild;
        if (row) tbody.appendChild(row);
        updateFleetLabelsFromDom();
        updateSaveButtonState();
      }});
    }}

    const pasteApply = document.getElementById("oe-paste-apply");
    if (pasteApply) {{
      pasteApply.addEventListener("click", function () {{
        const params = new URLSearchParams();
        params.set("oe_action", "paste");
        params.set("paste_text", (document.getElementById("oe-paste-area") || {{ value: "" }}).value || "");
        params.set("paste_mode", "append");
        appendFleetParams(params);
        oeNavigate(params);
      }});
    }}
  }}

  function ensureFleetEmptyState() {{
    const tbody = document.getElementById("oe-fleet-tbody");
    if (!tbody) return;
    if (tbody.querySelector("tr[data-fleet-row]")) return;
    if (document.getElementById("oe-fleet-empty")) return;
    const template = document.createElement("tbody");
    template.innerHTML = {json.dumps(fleet_empty_template)};
    const row = template.firstElementChild;
    if (row) tbody.appendChild(row);
  }}

  function wireFleetDelete() {{
    const tbody = document.getElementById("oe-fleet-tbody");
    if (!tbody) return;
    tbody.addEventListener("click", function (event) {{
      const btn = event.target.closest(".oe-fleet-delete");
      if (!btn) return;
      event.preventDefault();
      const row = btn.closest("tr[data-fleet-row]");
      if (row) row.remove();
      ensureFleetEmptyState();
      updateFleetLabelsFromDom();
      updateSaveButtonState();
    }});
  }}

  function wireFleetInputChanges() {{
    const tbody = document.getElementById("oe-fleet-tbody");
    if (!tbody) return;
    tbody.addEventListener("input", function () {{
      updateFleetLabelsFromDom();
      updateSaveButtonState();
    }});
  }}

  function wireSearch() {{
    const searchBtn = document.getElementById("oe-search-btn");
    if (!searchBtn) return;
    searchBtn.addEventListener("click", function (event) {{
      event.preventDefault();
      runSearch();
    }});
  }}

  function wireMatchesOnly() {{
    const box = document.getElementById("oe-matches-only");
    if (!box) return;
    box.addEventListener("change", function () {{
      renderMatchesOnlyFromCache();
    }});
  }}

  function wireDownload() {{
    const btn = document.getElementById("oe-download-csv");
    if (!btn) return;
    btn.addEventListener("click", function () {{
      const table = document.getElementById("oe-results-table");
      if (!table) return;
      const lines = [];
      table.querySelectorAll("tr").forEach(function (tr) {{
        const cells = Array.from(tr.querySelectorAll("th,td")).map(function (cell) {{
          const text = (cell.textContent || "").trim().replace(/"/g, '""');
          return '"' + text + '"';
        }});
        if (cells.length) lines.push(cells.join(","));
      }});
      if (lines.length < 2) return;
      const blob = new Blob([lines.join("\\n")], {{ type: "text/csv;charset=utf-8;" }});
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "object_explorer_results.csv";
      link.click();
      URL.revokeObjectURL(link.href);
    }});
  }}

  function init() {{
    wireSlider();
    wireHomeNav();
    wireFleetActions();
    wireFleetDelete();
    wireFleetInputChanges();
    syncSavedSnapshotFromStorage();
    updateSaveButtonState();
    wireSearch();
    wireMatchesOnly();
    wireDownload();
    maybeHydrateFromStorage();
  }}

  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", init);
  }} else {{
    init();
  }}
}})();
</script>
"""


def _object_type_select_options(selected: str) -> str:
    return "\n".join(
        f'<option{" selected" if obj_type == selected else ""}>{html.escape(obj_type)}</option>'
        for obj_type in OBJECT_TYPES
    )


def _wire_oe_document(source: str, view: ObjectExplorerView) -> str:
    doc = source
    home_clear_url = f"/?{OE_CLEAR_QUERY_PARAM}=1"
    db_label = f"{view.db_count} Database{'s' if view.db_count != 1 else ''} Configured"
    doc = re.sub(
        r"\d+ Databases Configured",
        f'<span id="oe-db-count-subheader">{db_label}</span>',
        doc,
        count=1,
    )

    doc = re.sub(
        r'<button[^>]*>\s*'
        r'<span class="material-symbols-outlined text-sm">arrow_back</span>\s*Home\s*</button>',
        (
            f'<a href="{home_clear_url}" id="oe-home-back" '
            'class="oe-home-link flex items-center gap-1 text-on-secondary-container hover:text-primary '
            'transition-colors text-sm font-medium no-underline">'
            '<span class="material-symbols-outlined text-sm">arrow_back</span> Home</a>'
        ),
        doc,
        count=1,
        flags=re.DOTALL,
    )

    fleet_label = f"Database Fleet ({view.db_count} database{'s' if view.db_count != 1 else ''})"
    doc = re.sub(
        r"Database Fleet \(\d+ databases?\)",
        f'<span id="oe-fleet-title">{fleet_label}</span>',
        doc,
        count=1,
    )

    doc = re.sub(
        r'(<input class="bg-surface border border-outline-variant px-sm py-1\.5 rounded focus:border-primary focus:ring-0 text-sm font-code-sm" type="text" )value="[^"]*"',
        rf'\1id="oe-username" value="{html.escape(view.username)}"',
        doc,
        count=1,
    )
    doc = re.sub(
        r'(<input class="bg-surface border border-outline-variant px-sm py-1\.5 rounded focus:border-primary focus:ring-0 text-sm" type="password" )value="[^"]*"',
        rf'\1id="oe-password" value="{html.escape(view.password)}"',
        doc,
        count=1,
    )

    if view.include_system:
        doc = doc.replace(
            '<input class="rounded border-outline-variant text-primary focus:ring-primary w-4 h-4" type="checkbox">',
            '<input id="oe-include-system" class="rounded border-outline-variant text-primary focus:ring-primary w-4 h-4" type="checkbox" checked>',
            1,
        )
    else:
        doc = doc.replace(
            '<input class="rounded border-outline-variant text-primary focus:ring-primary w-4 h-4" type="checkbox">',
            '<input id="oe-include-system" class="rounded border-outline-variant text-primary focus:ring-primary w-4 h-4" type="checkbox">',
            1,
        )

    doc = re.sub(
        r'(<span class="font-code-md text-primary font-bold">)\d+(</span>)',
        rf"\g<1>{view.max_workers}\g<2>",
        doc,
        count=1,
    )
    doc = re.sub(
        r'(<input class="w-full h-1\.5 bg-surface-container-high rounded-lg appearance-none cursor-pointer accent-primary" max="32" min="1" type="range" )value="\d+"',
        rf'\1id="oe-max-workers" value="{view.max_workers}"',
        doc,
        count=1,
    )

    doc = re.sub(
        r'(<input class="w-full bg-surface border border-outline-variant pl-10 pr-sm py-2 rounded focus:border-primary focus:ring-0 text-sm font-code-sm" placeholder="e\.g\. sp_refresh" type="text")',
        rf'\1 id="oe-filter-text" value="{html.escape(view.filter_text)}"',
        doc,
        count=1,
    )

    doc = re.sub(
        r'<select class="w-full bg-surface border border-outline-variant px-sm py-2 rounded focus:border-primary focus:ring-0 text-sm font-medium">\s*.*?\s*</select>',
        (
            '<select id="oe-object-type" class="w-full bg-surface border border-outline-variant '
            "px-sm py-2 rounded focus:border-primary focus:ring-0 text-sm font-medium\">\n"
            f"{_object_type_select_options(view.object_type)}\n"
            "</select>"
        ),
        doc,
        count=1,
        flags=re.DOTALL,
    )

    doc = _wire_match_operator(doc, view.operator)

    doc = re.sub(
        r'(<label class="flex items-center gap-2 cursor-pointer">\s*)'
        r'<input checked="" class="rounded border-outline-variant text-primary focus:ring-primary w-4 h-4" type="checkbox">'
        r'(\s*<span class="font-body-sm text-secondary font-medium">Matches only</span>)',
        (
            rf'\1<input id="oe-matches-only" '
            f'{"checked " if view.show_matches_only else ""}'
            r'class="rounded border-outline-variant text-primary focus:ring-primary w-4 h-4" type="checkbox">\2'
        ),
        doc,
        count=1,
        flags=re.DOTALL,
    )
    doc = doc.replace(
        '<button class="flex items-center gap-1.5 bg-surface border border-outline-variant px-3 py-1 rounded text-xs font-bold hover:bg-surface-container-high transition-colors">',
        '<button id="oe-download-csv" type="button" class="flex items-center gap-1.5 bg-surface border border-outline-variant px-3 py-1 rounded text-xs font-bold hover:bg-surface-container-high transition-colors">',
        1,
    )
    doc = doc.replace(
        "<!-- Main Results Table -->\n<div class=\"flex-1 overflow-auto custom-scrollbar\">\n<table class=\"w-full text-left border-collapse\">",
        '<!-- Main Results Table -->\n<div class="flex-1 overflow-auto custom-scrollbar">\n<table id="oe-results-table" class="w-full text-left border-collapse">',
        1,
    )

    doc = doc.replace(
        '<button class="bg-primary text-white font-bold px-lg py-2 rounded flex items-center gap-2 hover:bg-primary/90 active:scale-95 transition-all">\n                        Search all databases\n                    </button>',
        '<button id="oe-search-btn" type="button" class="bg-primary text-white font-bold px-lg py-2 rounded flex items-center gap-2 hover:bg-primary/90 active:scale-95 transition-all">Search all databases</button>',
        1,
    )

    doc = doc.replace(
        '<button class="px-3 py-1 text-xs font-semibold text-secondary hover:bg-surface-container-high rounded transition-colors">Reset</button>',
        '<button id="oe-reset-fleet" type="button" class="px-3 py-1 text-xs font-semibold text-secondary hover:bg-surface-container-high rounded transition-colors">Reset</button>',
        1,
    )
    doc = doc.replace(
        '<button class="px-3 py-1 text-xs font-semibold bg-primary text-white rounded hover:bg-primary/90 transition-colors">Save Fleet</button>',
        '<button id="oe-save-fleet" type="button" class="px-3 py-1 text-xs font-semibold bg-primary text-white rounded hover:bg-primary/90 transition-colors">Save Fleet</button>',
        1,
    )
    doc = doc.replace(
        '<textarea class="w-full h-24 bg-surface-container-low border border-outline-variant rounded font-code-sm p-2 text-xs focus:ring-0 focus:border-primary" placeholder="DB_NAME, HOST, PORT..."></textarea>',
        (
            '<textarea id="oe-paste-area" class="w-full h-24 bg-surface-container-low border border-outline-variant '
            'rounded font-code-sm p-2 text-xs focus:ring-0 focus:border-primary" '
            'placeholder="DB_NAME, HOST, PORT or jdbc:db2://host:port/db"></textarea>'
            '<button id="oe-paste-apply" type="button" '
            'class="mt-sm px-3 py-1 text-xs font-semibold bg-primary text-white rounded hover:bg-primary/90 transition-colors">'
            "Apply pasted rows</button>"
        ),
        1,
    )
    doc = doc.replace(
        '<tbody class="divide-y divide-outline-variant">',
        '<tbody id="oe-fleet-tbody" class="divide-y divide-outline-variant">',
        1,
    )
    doc = doc.replace(
        '<button class="text-primary font-bold text-xs flex items-center gap-1 hover:underline">',
        '<button id="oe-add-row" type="button" class="text-primary font-bold text-xs flex items-center gap-1 hover:underline">',
        1,
    )

    fleet_rows = view.fleet_rows or []
    doc = _replace_first_tbody(doc, _fleet_tbody_rows(fleet_rows))
    doc = _wire_results_panel(doc, view)

    if _OE_MICRO_SCRIPT.search(doc):
        doc = _OE_MICRO_SCRIPT.sub("", doc, count=1)

    doc = doc.replace("</body>", _oe_bridge_script(view) + _FULL_HEIGHT_SCRIPT + "</body>")
    return doc


def _wire_match_operator(doc: str, operator: str) -> str:
    plain = '<input class="text-primary focus:ring-primary w-3.5 h-3.5" name="match_mode" type="radio">'
    checked = '<input checked="" class="text-primary focus:ring-primary w-3.5 h-3.5" name="match_mode" type="radio">'
    doc = doc.replace(
        '<input checked="" class="text-primary focus:ring-primary w-3.5 h-3.5" name="match_mode" type="radio">',
        plain,
    )
    try:
        pick = MATCH_ORDER.index(operator)
    except ValueError:
        pick = 0
    idx = 0

    def _radio_sub(_match: re.Match[str]) -> str:
        nonlocal idx
        current = idx
        idx += 1
        return checked if current == pick else plain

    return re.sub(re.escape(plain), _radio_sub, doc, count=len(MATCH_ORDER))


def render_object_explorer_page(view: ObjectExplorerView) -> None:
    """Exact stitch 02-object-explorer index.html — full document with live data."""
    inject_shell_component(tailwind_config_source="object_explorer")
    doc = _wire_oe_document(_read_html("object_explorer"), view)
    st.markdown(f"<style>{shell_iframe_css()}</style>", unsafe_allow_html=True)
    components.html(doc, height=900, scrolling=False)
