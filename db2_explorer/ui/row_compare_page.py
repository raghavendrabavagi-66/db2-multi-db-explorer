"""Row Compare stitch pages — setup (01) and workspace (05)."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from db2_explorer.api.register import (
    rc_list_azure_databases_api_url,
    rc_test_azure_api_url,
    rc_test_db2_api_url,
)
from db2_explorer.ui.stitch_shell import (
    _read_html,
    inject_shell_component,
    shell_iframe_css,
)

ROW_COMPARE_PAGE = "/Row_Compare"
_HOME_URL = "/"

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

_RC_SETUP_MICRO = re.compile(
    r'<script id="rc-setup-bridge-placeholder"></script>',
    re.DOTALL,
)


@dataclass
class RowCompareSetupView:
    db2_database: str = ""
    db2_host: str = ""
    db2_port: int = 50000
    db2_user: str = ""
    db2_password: str = ""
    az_server: str = ""
    az_database: str = ""
    az_database_options: list[str] = field(default_factory=list)
    az_auth: str = "entra"
    az_trust_cert: bool = True
    toast_message: str = ""
    toast_error: bool = False


@dataclass
class RowCompareWorkspaceView:
    db2_database: str = ""
    db2_host: str = ""
    db2_port: int = 50000
    az_server: str = ""
    az_database: str = ""
    az_auth_label: str = ""
    target_table_mode: str = "original"
    compare_scope: str = "all"
    metrics: dict[str, Any] = field(default_factory=dict)
    result_rows_html: str = ""
    has_results: bool = False
    status_message: str = ""
    toast_message: str = ""
    toast_error: bool = False


def _auth_entra_checked(auth: str) -> str:
    return "checked" if auth != "windows" else ""


def _auth_windows_checked(auth: str) -> str:
    return "checked" if auth == "windows" else ""


def _azure_database_options_html(selected: str, databases: list[str]) -> str:
    parts = ['<option value="">Select a database…</option>']
    names: list[str] = []
    if selected and selected not in databases:
        names.append(selected)
    names.extend(databases)
    seen: set[str] = set()
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        sel = " selected" if name == selected else ""
        esc = html.escape(name)
        parts.append(f'<option value="{esc}"{sel}>{esc}</option>')
    return "".join(parts)


def _rc_setup_bridge_script(view: RowCompareSetupView) -> str:
    test_db2_url = rc_test_db2_api_url()
    test_az_url = rc_test_azure_api_url()
    list_az_url = rc_list_azure_databases_api_url()
    return f"""
<script>
(function () {{
  const RC_PAGE = {json.dumps(ROW_COMPARE_PAGE)};
  const HOME_URL = {json.dumps(_HOME_URL)};
  const TEST_DB2_URL = {json.dumps(test_db2_url)};
  const TEST_AZ_URL = {json.dumps(test_az_url)};
  const LIST_AZ_URL = {json.dumps(list_az_url)};

  function apiUrl(pathOrFull) {{
    if (pathOrFull.startsWith("http")) return pathOrFull;
    try {{
      const origin = window.top.location.origin;
      if (origin && origin !== "null") return origin + pathOrFull;
    }} catch (err) {{}}
    return pathOrFull;
  }}

  function rcPagePath() {{
    try {{
      const topPath = window.top.location.pathname || "";
      if (topPath.indexOf("Row_Compare") >= 0) return topPath;
    }} catch (err) {{}}
    return RC_PAGE;
  }}

  function rcNavigate(params) {{
    const url = rcPagePath() + "?" + params.toString();
    window.parent.postMessage({{ type: "stitch-oe-nav", url: url }}, "*");
    if (window.top && window.top !== window) {{
      window.top.postMessage({{ type: "stitch-oe-nav", url: url }}, "*");
    }}
    try {{
      window.top.location.href = url;
    }} catch (err) {{}}
  }}

  function toast(msg, isError) {{
    const el = document.getElementById("rc-toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] px-lg py-sm rounded shadow-lg text-body-sm font-medium "
      + (isError ? "bg-error-container text-on-error-container" : "bg-primary text-on-primary");
    el.style.display = "block";
    setTimeout(function () {{ el.style.display = "none"; }}, 5000);
  }}

  function collectDb2() {{
    return {{
      database: (document.getElementById("rc-db2-database") || {{ value: "" }}).value.trim(),
      host: (document.getElementById("rc-db2-host") || {{ value: "" }}).value.trim(),
      port: (document.getElementById("rc-db2-port") || {{ value: "50000" }}).value.trim(),
      username: (document.getElementById("rc-db2-user") || {{ value: "" }}).value.trim(),
      password: (document.getElementById("rc-db2-password") || {{ value: "" }}).value,
    }};
  }}

  function collectAzure() {{
    const authEl = document.querySelector('input[name="auth_type_modal"]:checked');
    return {{
      server: (document.getElementById("rc-az-server") || {{ value: "" }}).value.trim(),
      database: (document.getElementById("rc-az-database") || {{ value: "" }}).value.trim(),
      auth_method: authEl ? authEl.value : "entra",
      trust_server_certificate: !!(document.getElementById("rc-az-trust-cert") || {{}}).checked,
    }};
  }}

  async function postJson(url, body) {{
    const res = await fetch(apiUrl(url), {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(body),
    }});
    let payload;
    try {{
      payload = await res.json();
    }} catch (err) {{
      throw new Error("Invalid server response (HTTP " + res.status + ").");
    }}
    if (!payload.error && !payload.ok && !res.ok) {{
      payload.error = "Request failed (HTTP " + res.status + ").";
    }}
    return payload;
  }}

  function setAzureDatabaseOptions(names, selected) {{
    const sel = document.getElementById("rc-az-database");
    if (!sel) return;
    const keep = selected || sel.value || "";
    sel.innerHTML = '<option value="">Select a database…</option>';
    names.forEach(function (name) {{
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      if (name === keep) opt.selected = true;
      sel.appendChild(opt);
    }});
    if (keep && !names.includes(keep)) {{
      const opt = document.createElement("option");
      opt.value = keep;
      opt.textContent = keep;
      opt.selected = true;
      sel.insertBefore(opt, sel.options[1] || null);
    }}
  }}

  async function refreshAzureDatabases() {{
    const server = (document.getElementById("rc-az-server") || {{ value: "" }}).value.trim();
    if (!server) {{
      toast("Enter Azure SQL Server first.", true);
      return;
    }}
    const btn = document.getElementById("rc-az-refresh-dbs");
    const icon = btn ? btn.querySelector(".material-symbols-outlined") : null;
    if (btn) btn.disabled = true;
    if (icon) icon.classList.add("animate-spin");
    try {{
      const authEl = document.querySelector('input[name="auth_type_modal"]:checked');
      const payload = await postJson(LIST_AZ_URL, {{
        server: server,
        auth_method: authEl ? authEl.value : "entra",
        trust_server_certificate: !!(document.getElementById("rc-az-trust-cert") || {{}}).checked,
      }});
      if (!payload.ok) {{
        toast(payload.error || "Could not list databases.", true);
        return;
      }}
      const current = (document.getElementById("rc-az-database") || {{ value: "" }}).value;
      setAzureDatabaseOptions(payload.databases || [], current);
      toast(payload.message || "Databases loaded.", false);
    }} catch (err) {{
      toast(err.message || "Database list request failed.", true);
    }} finally {{
      if (btn) btn.disabled = false;
      if (icon) icon.classList.remove("animate-spin");
    }}
  }}

  async function testDb2() {{
    const btn = document.getElementById("rc-db2-test");
    const orig = btn ? btn.innerHTML : "";
    if (btn) {{ btn.disabled = true; btn.innerHTML = "Testing…"; }}
    try {{
      const payload = await postJson(TEST_DB2_URL, collectDb2());
      toast(payload.message || payload.error || "Test failed.", !payload.ok);
    }} catch (err) {{
      toast(err.message || "DB2 test request failed.", true);
    }} finally {{
      if (btn) {{ btn.disabled = false; btn.innerHTML = orig; }}
    }}
  }}

  async function testAzure() {{
    const btn = document.getElementById("rc-az-test");
    const orig = btn ? btn.innerHTML : "";
    if (btn) {{ btn.disabled = true; btn.innerHTML = "Testing…"; }}
    try {{
      const payload = await postJson(TEST_AZ_URL, collectAzure());
      toast(payload.message || payload.error || "Test failed.", !payload.ok);
    }} catch (err) {{
      toast(err.message || "Azure test request failed.", true);
    }} finally {{
      if (btn) {{ btn.disabled = false; btn.innerHTML = orig; }}
    }}
  }}

  function connectAndCompare() {{
    const db2 = collectDb2();
    const az = collectAzure();
    if (!db2.database || !db2.host || !db2.username || !db2.password) {{
      toast("Complete all DB2 source fields.", true);
      return;
    }}
    if (!az.server || !az.database) {{
      toast("Complete Azure server and database.", true);
      return;
    }}
    const params = new URLSearchParams();
    params.set("rc_action", "connect");
    params.set("cmp_db2_database", db2.database);
    params.set("cmp_db2_host", db2.host);
    params.set("cmp_db2_port", db2.port || "50000");
    params.set("cmp_db2_user", db2.username);
    params.set("cmp_db2_password", db2.password);
    params.set("cmp_az_server", az.server);
    params.set("cmp_az_database", az.database);
    params.set("cmp_az_auth", az.auth_method);
    params.set("cmp_az_trust_cert", az.trust_server_certificate ? "1" : "0");
    rcNavigate(params);
  }}

  function wireSetup() {{
    const db2Test = document.getElementById("rc-db2-test");
    if (db2Test) db2Test.addEventListener("click", function (e) {{ e.preventDefault(); testDb2(); }});
    const azTest = document.getElementById("rc-az-test");
    if (azTest) azTest.addEventListener("click", function (e) {{ e.preventDefault(); testAzure(); }});
    const refreshDbs = document.getElementById("rc-az-refresh-dbs");
    if (refreshDbs) refreshDbs.addEventListener("click", function (e) {{ e.preventDefault(); refreshAzureDatabases(); }});
    const compareBtn = document.getElementById("rc-compare-btn");
    if (compareBtn) compareBtn.addEventListener("click", function (e) {{ e.preventDefault(); connectAndCompare(); }});
    const closeBtn = document.getElementById("rc-close-btn");
    if (closeBtn) closeBtn.addEventListener("click", function (e) {{
      e.preventDefault();
      try {{ window.top.location.href = HOME_URL; }} catch (err) {{ rcNavigate(new URLSearchParams()); }}
    }});
  }}

  wireSetup();
  {f'toast({json.dumps(view.toast_message)}, {json.dumps(view.toast_error)});' if view.toast_message else ''}
}})();
</script>
<div id="rc-toast" style="display:none"></div>
"""


def _wire_rc_setup_document(source: str, view: RowCompareSetupView) -> str:
    doc = source
    doc = doc.replace(
        'id="rc-db2-database" class="flex-1 studio-input" type="text" value=""',
        f'id="rc-db2-database" class="flex-1 studio-input" type="text" value="{html.escape(view.db2_database)}"',
    )
    doc = doc.replace(
        'id="rc-db2-host" class="w-full studio-input" placeholder="10.0.4.12" type="text"',
        f'id="rc-db2-host" class="w-full studio-input" placeholder="10.0.4.12" type="text" value="{html.escape(view.db2_host)}"',
    )
    doc = doc.replace(
        'id="rc-db2-port" class="w-full studio-input" type="text" value="50000"',
        f'id="rc-db2-port" class="w-full studio-input" type="text" value="{view.db2_port}"',
    )
    doc = doc.replace(
        'id="rc-db2-user" class="w-full studio-input" type="text" value=""',
        f'id="rc-db2-user" class="w-full studio-input" type="text" value="{html.escape(view.db2_user)}"',
    )
    doc = doc.replace(
        'id="rc-db2-password" class="w-full studio-input" type="password" value=""',
        f'id="rc-db2-password" class="w-full studio-input" type="password" value="{html.escape(view.db2_password)}"',
    )
    doc = re.sub(
        r'id="rc-az-server" class="w-full h-10 px-md border border-outline[^"]*" placeholder="[^"]*" type="text"',
        f'id="rc-az-server" class="w-full h-10 px-md border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" placeholder="az-db-prod-sql.database.windows.net" type="text" value="{html.escape(view.az_server)}"',
        doc,
        count=1,
    )
    doc = re.sub(
        r'(<select id="rc-az-database"[^>]*>).*?(</select>)',
        rf'\1{_azure_database_options_html(view.az_database, view.az_database_options)}\2',
        doc,
        count=1,
        flags=re.DOTALL,
    )
    if view.az_trust_cert:
        doc = doc.replace(
            '<input id="rc-az-trust-cert" type="checkbox" class="rounded',
            '<input id="rc-az-trust-cert" type="checkbox" checked class="rounded',
            1,
        )
    doc = doc.replace(
        f'<input id="rc-auth-entra" type="radio" name="auth_type_modal" value="entra" class="w-4 h-4 text-primary border-outline focus:ring-primary" checked="">',
        f'<input id="rc-auth-entra" type="radio" name="auth_type_modal" value="entra" class="w-4 h-4 text-primary border-outline focus:ring-primary" {_auth_entra_checked(view.az_auth)}>',
        1,
    )
    doc = doc.replace(
        '<input id="rc-auth-windows" type="radio" name="auth_type_modal" value="windows" class="w-4 h-4 text-primary border-outline focus:ring-primary">',
        f'<input id="rc-auth-windows" type="radio" name="auth_type_modal" value="windows" class="w-4 h-4 text-primary border-outline focus:ring-primary" {_auth_windows_checked(view.az_auth)}>',
        1,
    )
    doc = _RC_SETUP_MICRO.sub(_rc_setup_bridge_script(view), doc, count=1)
    doc = doc.replace("</body>", _FULL_HEIGHT_SCRIPT + "</body>")
    return doc


_RC_WORKSPACE_MICRO = re.compile(
    r'<script id="rc-workspace-bridge-placeholder"></script>',
    re.DOTALL,
)


def _table_type_staging_checked(mode: str) -> str:
    return "checked" if mode == "staging" else ""


def _table_type_original_checked(mode: str) -> str:
    return "checked" if mode != "staging" else ""


def _status_badge_html(status: str) -> str:
    s = (status or "").upper()
    if s == "MATCH":
        return '<span class="bg-emerald-100 text-emerald-700 px-sm py-0.5 rounded text-[10px] font-bold tracking-wider">MATCH</span>'
    if s in {"MISMATCH", "DELTA"}:
        return '<span class="bg-amber-100 text-amber-700 px-sm py-0.5 rounded text-[10px] font-bold tracking-wider">MISMATCH</span>'
    return '<span class="bg-red-100 text-red-700 px-sm py-0.5 rounded text-[10px] font-bold tracking-wider">FAILED</span>'


def _comparison_rows_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return (
            '<tr><td colspan="5" class="px-md py-4 text-center text-secondary font-body-sm">'
            "No comparison results yet. Click RUN COMPARISON.</td></tr>"
        )
    parts: list[str] = []
    for row in rows:
        name = html.escape(str(row.get("Table", "")))
        src = row.get("Source Count", "N/A")
        tgt = row.get("Target Count", "N/A")
        delta = row.get("Delta", "N/A")
        status = _status_badge_html(str(row.get("Status", "")))
        src_s = html.escape(str(src))
        tgt_s = html.escape(str(tgt))
        delta_s = html.escape(str(delta))
        parts.append(
            f'<tr class="hover:bg-surface-container transition-colors">'
            f'<td class="px-md py-2 font-code-sm">{name}</td>'
            f'<td class="px-md py-2 text-right">{src_s}</td>'
            f'<td class="px-md py-2 text-right">{tgt_s}</td>'
            f'<td class="px-md py-2 text-right">{delta_s}</td>'
            f'<td class="px-md py-2">{status}</td></tr>'
        )
    return "".join(parts)


def _rc_workspace_bridge_script(view: RowCompareWorkspaceView) -> str:
    return f"""
<script>
(function () {{
  const RC_PAGE = {json.dumps(ROW_COMPARE_PAGE)};

  function rcPagePath() {{
    try {{
      const topPath = window.top.location.pathname || "";
      if (topPath.indexOf("Row_Compare") >= 0) return topPath;
    }} catch (err) {{}}
    return RC_PAGE;
  }}

  function rcNavigate(params) {{
    const url = rcPagePath() + "?" + params.toString();
    window.parent.postMessage({{ type: "stitch-oe-nav", url: url }}, "*");
    try {{ window.top.location.href = url; }} catch (err) {{}}
  }}

  function toast(msg, isError) {{
    const el = document.getElementById("rc-toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] px-lg py-sm rounded shadow-lg text-body-sm "
      + (isError ? "bg-error-container text-on-error-container" : "bg-primary text-on-primary");
    el.style.display = "block";
    setTimeout(function () {{ el.style.display = "none"; }}, 5000);
  }}

  const editBtn = document.getElementById("rc-edit-creds");
  if (editBtn) editBtn.addEventListener("click", function (e) {{
    e.preventDefault();
    const p = new URLSearchParams();
    p.set("rc_action", "edit");
    rcNavigate(p);
  }});

  const runBtn = document.getElementById("rc-run-btn");
  if (runBtn) runBtn.addEventListener("click", function (e) {{
    e.preventDefault();
    const staging = document.querySelector('input[name="table_type"][value="staging"]');
    const mode = staging && staging.checked ? "staging" : "original";
    const p = new URLSearchParams();
    p.set("rc_action", "run");
    p.set("cmp_target_table_mode", mode);
    rcNavigate(p);
  }});

  {f'toast({json.dumps(view.toast_message)}, {json.dumps(view.toast_error)});' if view.toast_message else ''}
}})();
</script>
<div id="rc-toast" style="display:none"></div>
"""


def _wire_rc_workspace_document(source: str, view: RowCompareWorkspaceView) -> str:
    doc = source
    m = view.metrics
    replacements = [
        (">142<", f">{m.get('tables_source', 0)}<"),
        (">128<", f">{m.get('matched', 0)}<"),
        (">12<", f">{m.get('mismatched', 0)}<"),
        (">2<", f">{m.get('missing', 0)}<"),
        (">1.2B<", f">{m.get('rows_label', '—')}<"),
    ]
    for old, new in replacements:
        doc = doc.replace(old, new, 1)

    doc = re.sub(
        r"<tbody class=\"font-body-sm text-body-sm divide-y divide-outline-variant\">.*?</tbody>",
        f'<tbody id="rc-results-tbody" class="font-body-sm text-body-sm divide-y divide-outline-variant">{view.result_rows_html}</tbody>',
        doc,
        count=1,
        flags=re.DOTALL,
    )
    doc = doc.replace(
        'class="w-4 h-4 text-primary border-outline-variant focus:ring-primary" name="table_type" type="radio" value="staging"><span class="text-body-sm">Staging tables</span>',
        f'class="w-4 h-4 text-primary border-outline-variant focus:ring-primary" name="table_type" type="radio" value="staging" {_table_type_staging_checked(view.target_table_mode)}><span class="text-body-sm">Staging tables</span>',
        1,
    )
    doc = doc.replace(
        'checked="" class="w-4 h-4 text-primary border-outline-variant focus:ring-primary" name="table_type" type="radio" value="original"><span class="text-body-sm">Main tables</span>',
        f'class="w-4 h-4 text-primary border-outline-variant focus:ring-primary" name="table_type" type="radio" value="original" {_table_type_original_checked(view.target_table_mode)}><span class="text-body-sm">Main tables</span>',
        1,
    )
    doc = _RC_WORKSPACE_MICRO.sub(_rc_workspace_bridge_script(view), doc, count=1)
    doc = doc.replace("</body>", _FULL_HEIGHT_SCRIPT + "</body>")
    return doc


def render_row_compare_setup_page(view: RowCompareSetupView) -> None:
    inject_shell_component(tailwind_config_source="row_setup")
    # Bust cache so stitch HTML edits are picked up without restarting Streamlit.
    from db2_explorer.ui import stitch_shell as _shell

    _shell._HTML_CACHE.pop("row_setup", None)
    doc = _wire_rc_setup_document(_read_html("row_setup"), view)
    st.markdown(f"<style>{shell_iframe_css()}</style>", unsafe_allow_html=True)
    components.html(doc, height=900, scrolling=False)


def render_row_compare_workspace_page(view: RowCompareWorkspaceView) -> None:
    inject_shell_component(tailwind_config_source="row_workspace")
    doc = _wire_rc_workspace_document(_read_html("row_workspace"), view)
    st.markdown(f"<style>{shell_iframe_css()}</style>", unsafe_allow_html=True)
    components.html(doc, height=900, scrolling=False)
