"""Client-side layout sync for Object Explorer hero panels."""

from __future__ import annotations

import streamlit.components.v1 as components

# JS targets for panel-fill table height sync.
FLEET_EDITOR_KEY = "db_editor"
RESULTS_TABLE_KEY = "oe_results_table"

_LAYOUT_SYNC_SCRIPT = """
(function () {
  const doc = window.parent.document;
  const root = doc.documentElement;
  let timer = null;

  function heroBorder(panelKey) {
    const panel = doc.querySelector(".st-key-" + panelKey);
    if (!panel) return null;
    return panel.querySelector('[data-testid="stVerticalBlockBorderWrapper"]') || panel;
  }

  function syncResultsHeight() {
    const fleetBorder = heroBorder("oe_fleet_panel");
    const resultsPanel = doc.querySelector(".st-key-oe_results_panel");
    const resultsBorder = heroBorder("oe_results_panel");
    if (!fleetBorder || !resultsPanel || !resultsBorder) return;

    const fleetBottom = fleetBorder.getBoundingClientRect().bottom;
    const resultsTop = resultsBorder.getBoundingClientRect().top;
    const targetH = Math.max(160, Math.floor(fleetBottom - resultsTop - 8));
    if (targetH < 120) return;

    root.style.setProperty("--oe-results-panel-h", targetH + "px");
    resultsPanel.style.height = targetH + "px";
    resultsPanel.style.maxHeight = targetH + "px";
    resultsPanel.style.minHeight = "0";
    resultsBorder.style.height = targetH + "px";
    resultsBorder.style.maxHeight = targetH + "px";
    resultsBorder.style.minHeight = "0";
  }

  function panelBorder(panel) {
    if (!panel) return null;
    return panel.querySelector('[data-testid="stVerticalBlockBorderWrapper"]') || panel;
  }

  function availableHeight(anchor, panel) {
    const border = panelBorder(panel);
    if (!border || !anchor) return null;
    const bottom = border.getBoundingClientRect().bottom;
    const top = anchor.getBoundingClientRect().top;
    return Math.max(220, Math.floor(bottom - top - 10));
  }

  function applyHeight(wrap, widget, h, cssVar) {
    root.style.setProperty(cssVar, h + "px");
    if (wrap) {
      wrap.style.flex = "1 1 auto";
      wrap.style.minHeight = "0";
      wrap.style.display = "flex";
      wrap.style.flexDirection = "column";
    }
    widget.style.flex = "1 1 auto";
    widget.style.minHeight = "0";
    widget.style.width = "100%";
    widget.style.height = h + "px";
    widget.style.maxHeight = h + "px";
    widget.style.overflow = "hidden";
    widget.querySelectorAll(
      '[data-testid="stVerticalBlock"], [data-testid="element-container"], ' +
        '[data-testid="stDataFrameResizable"]'
    ).forEach((el) => {
      el.style.flex = "1 1 auto";
      el.style.minHeight = "0";
      el.style.height = h + "px";
      el.style.maxHeight = h + "px";
      el.style.overflow = "hidden";
    });
    const glideHost = widget.querySelector(":scope > div");
    if (glideHost) {
      glideHost.style.height = h + "px";
      glideHost.style.maxHeight = h + "px";
    }
  }

  function syncFleetEditor() {
    const panel = doc.querySelector(".st-key-oe_fleet_panel");
    const editorWrap = doc.querySelector(".st-key-db_editor");
    const widget = editorWrap
      ? editorWrap.querySelector('[data-testid="stDataEditor"]')
      : null;
    if (!panel || !widget) return;
    const h = availableHeight(widget, panel);
    if (!h) return;
    applyHeight(editorWrap, widget, h, "--oe-fleet-table-h");
  }

  function syncResultsTable() {
    const wrap = doc.querySelector(".st-key-oe_results_table");
    if (!wrap) return;
    const widget = wrap.querySelector('[data-testid="stDataFrame"]');
    const panel = wrap.closest(".st-key-oe_results_panel");
    if (!widget || !panel) return;
    const h = availableHeight(widget, panel);
    if (!h) return;
    applyHeight(wrap, widget, h, "--oe-results-table-h");
  }

  function syncAll() {
    syncResultsHeight();
    syncFleetEditor();
    syncResultsTable();
    window.parent.dispatchEvent(new Event("resize"));
  }

  function schedule() {
    if (timer) window.parent.clearTimeout(timer);
    timer = window.parent.setTimeout(() => {
      window.parent.requestAnimationFrame(() => {
        syncAll();
        window.parent.requestAnimationFrame(syncAll);
      });
    }, 40);
  }

  schedule();
  [100, 300, 600, 1200].forEach((ms) => window.parent.setTimeout(schedule, ms));
  window.parent.addEventListener("resize", schedule);
  const app = doc.querySelector(".stApp");
  if (app && window.parent.MutationObserver) {
    new window.parent.MutationObserver(schedule).observe(app, {
      childList: true,
      subtree: true,
      attributes: true,
    });
  }
})();
"""


def inject_layout_sync() -> None:
    """Inject zero-height iframe that syncs hero panel and table heights after paint."""
    components.html(f"<script>{_LAYOUT_SYNC_SCRIPT}</script>", height=0)
