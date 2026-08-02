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
    rc_create_bind_api_url,
    rc_list_azure_databases_api_url,
    rc_run_comparison_api_url,
    rc_save_connect_api_url,
    rc_test_db2_api_url,
)
from db2_explorer.ui.rc_session import row_compare_home_clear_url
from db2_explorer.ui.stitch_shell import (
    _read_html,
    inject_shell_component,
    shell_iframe_css,
)

ROW_COMPARE_PAGE = "/Row_Compare"
_HOME_CLEAR_URL = row_compare_home_clear_url()

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

_WORKSPACE_FRAME_HEIGHT_SCRIPT = """
<script>
(function () {
  function parentViewportHeight() {
    try {
      var h = window.parent.innerHeight;
      if (h && h > 0) return h;
    } catch (err) {}
    try {
      var topH = window.top.innerHeight;
      if (topH && topH > 0) return topH;
    } catch (err2) {}
    return window.innerHeight;
  }
  function syncRcFrameHeight() {
    var h = parentViewportHeight();
    window.parent.postMessage({ type: "streamlit:setFrameHeight", height: h }, "*");
  }
  window.syncRcFrameHeight = syncRcFrameHeight;
  syncRcFrameHeight();
  window.addEventListener("load", syncRcFrameHeight);
  window.addEventListener("resize", syncRcFrameHeight);
  try {
    window.parent.addEventListener("resize", syncRcFrameHeight);
  } catch (err) {}
})();
</script>
"""

_RC_WORKSPACE_SHELL_CSS = """
html.stitch-shell,
html.stitch-shell body,
html.stitch-shell #root {
    overflow: hidden !important;
    height: 100vh !important;
    max-height: 100vh !important;
}
html.stitch-shell [data-testid="stAppViewContainer"],
html.stitch-shell [data-testid="stAppViewContainer"] > section,
html.stitch-shell [data-testid="stMain"],
html.stitch-shell [data-testid="stMainBlockContainer"] {
    overflow: hidden !important;
    height: 100vh !important;
    max-height: 100vh !important;
}
html.stitch-shell iframe:not([height="0"]):not([height="1"]) {
    height: 100vh !important;
    max-height: 100vh !important;
    min-height: 0 !important;
}
"""

_RC_SETUP_MICRO = re.compile(
    r'<script id="rc-setup-bridge-placeholder"></script>',
    re.DOTALL,
)

_RC_AZ_SERVER_MICRO = re.compile(
    r'id="rc-az-server" class="w-full h-10 px-md border border-outline[^"]*" placeholder="[^"]*" type="text"',
)

_RC_AZ_DATABASE_MICRO = re.compile(
    r'(<select id="rc-az-database"[^>]*>).*?(</select>)',
    re.DOTALL,
)

_TBODY_MICRO = re.compile(
    r'<tbody class="font-body-sm text-body-sm divide-y divide-outline-variant">.*?</tbody>',
    re.DOTALL,
)


def _js_literal(value: object) -> str:
    """JSON for embedding in generated JS; keep Unicode literal (avoid \\u in output)."""
    return json.dumps(value, ensure_ascii=False)


def _regex_inject(pattern: re.Pattern[str], repl: str, doc: str, *, count: int = 0) -> str:
    """Regex substitute without interpreting backslashes in ``repl`` as escapes."""
    return pattern.sub(lambda _match: repl, doc, count=count)


def _az_server_input_html(server: str) -> str:
    return (
        'id="rc-az-server" class="w-full h-10 px-md border border-outline focus:border-primary '
        f'focus:ring-1 focus:ring-primary rounded bg-white text-body-md" '
        f'placeholder="az-db-prod-sql.database.windows.net" type="text" value="{html.escape(server)}"'
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
    edit_mode: bool = False
    rc_sid: str = ""
    rc_token: str = ""
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
    result_tbody_views: dict[str, str] = field(default_factory=dict)
    has_results: bool = False
    rc_sid: str = ""
    rc_token: str = ""
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
    list_az_url = rc_list_azure_databases_api_url()
    save_connect_url = rc_save_connect_api_url()
    return f"""
<script>
(function () {{
  const RC_PAGE = {json.dumps(ROW_COMPARE_PAGE)};
  const HOME_CLEAR_URL = {json.dumps(_HOME_CLEAR_URL)};
  const TEST_DB2_URL = {json.dumps(test_db2_url)};
  const LIST_AZ_URL = {json.dumps(list_az_url)};
  const SAVE_CONNECT_URL = {json.dumps(save_connect_url)};
  const RC_SID_KEY = "rc_sid";
  const RC_TOKEN_KEY = "rc_token";
  const EDIT_MODE = {json.dumps(view.edit_mode)};

  function rcSessionToken() {{
    try {{
      return sessionStorage.getItem(RC_TOKEN_KEY) || "";
    }} catch (err) {{
      return "";
    }}
  }}

  function setRcSessionToken(token) {{
    try {{
      if (token) sessionStorage.setItem(RC_TOKEN_KEY, token);
    }} catch (err) {{}}
  }}

  (function syncServerSession() {{
    var sid = {_js_literal(view.rc_sid)};
    var token = {_js_literal(view.rc_token)};
    if (sid) sessionStorage.setItem(RC_SID_KEY, sid);
    if (token) setRcSessionToken(token);
  }})();

  function rcSessionId() {{
    try {{
      let sid = sessionStorage.getItem(RC_SID_KEY);
      if (!sid) {{
        sid = (window.crypto && window.crypto.randomUUID)
          ? window.crypto.randomUUID()
          : "rc-" + Date.now() + "-" + Math.random().toString(16).slice(2);
        sessionStorage.setItem(RC_SID_KEY, sid);
      }}
      return sid;
    }} catch (err) {{
      return "rc-" + Date.now();
    }}
  }}

  function navigateBackToWorkspace() {{
    const p = new URLSearchParams();
    p.set("rc_action", "back");
    rcNavigate(p);
  }}

  function navigateHomeClear() {{
    window.parent.postMessage({{ type: "stitch-oe-nav", url: HOME_CLEAR_URL }}, "*");
    if (window.top && window.top !== window) {{
      window.top.postMessage({{ type: "stitch-oe-nav", url: HOME_CLEAR_URL }}, "*");
    }}
    try {{
      window.top.location.href = HOME_CLEAR_URL;
    }} catch (err) {{}}
  }}

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

  async function loadAzureDatabases() {{
    const server = (document.getElementById("rc-az-server") || {{ value: "" }}).value.trim();
    if (!server) {{
      toast("Enter Azure SQL Server first.", true);
      return;
    }}
    setAzLoadState("loading");
    try {{
      const authEl = document.querySelector('input[name="auth_type_modal"]:checked');
      const payload = await postJson(LIST_AZ_URL, {{
        server: server,
        auth_method: authEl ? authEl.value : "entra",
        trust_server_certificate: !!(document.getElementById("rc-az-trust-cert") || {{}}).checked,
      }});
      if (!payload.ok) {{
        azVerifiedSnapshot = null;
        azLoadedCount = 0;
        setAzLoadState("failed");
        toast(payload.error || "Could not list databases.", true);
        return;
      }}
      const databases = payload.databases || [];
      const current = (document.getElementById("rc-az-database") || {{ value: "" }}).value;
      setAzureDatabaseOptions(databases, current);
      azVerifiedSnapshot = azConnectionFingerprint();
      azLoadedCount = databases.length;
      setAzLoadState("verified");
      toast(payload.message || "Databases loaded.", false);
    }} catch (err) {{
      azVerifiedSnapshot = null;
      azLoadedCount = 0;
      setAzLoadState("failed");
      toast(err.message || "Database list request failed.", true);
    }}
  }}

  const DB2_BTN_BASE = "w-full h-10 font-title-sm rounded transition-colors flex items-center justify-center gap-sm";
  const DB2_BTN_IDLE = DB2_BTN_BASE + " border border-primary text-primary hover:bg-surface-container-low";
  const DB2_BTN_SUCCESS = DB2_BTN_BASE + " bg-emerald-600 text-white border border-emerald-600 hover:brightness-110";
  const DB2_BTN_FAILED = DB2_BTN_BASE + " border border-red-600 text-red-700 bg-red-50";
  const DB2_BTN_TESTING = DB2_BTN_BASE + " border border-primary text-primary opacity-70 cursor-wait";
  const DB2_FIELD_IDS = ["rc-db2-database", "rc-db2-host", "rc-db2-port", "rc-db2-user", "rc-db2-password"];

  let db2VerifiedSnapshot = null;
  let db2FailTimer = null;

  let azVerifiedSnapshot = null;
  let azLoadedCount = 0;
  let azFailTimer = null;

  function azConnectionFingerprint() {{
    const authEl = document.querySelector('input[name="auth_type_modal"]:checked');
    return JSON.stringify([
      (document.getElementById("rc-az-server") || {{ value: "" }}).value.trim(),
      authEl ? authEl.value : "entra",
      !!(document.getElementById("rc-az-trust-cert") || {{}}).checked,
    ]);
  }}

  function azIdleHtml() {{
    return '<span class="material-symbols-outlined text-[20px]">refresh</span>Load databases';
  }}

  function azSuccessHtml(count) {{
    const label = count === 1 ? "database" : "databases";
    return '<span class="material-symbols-outlined text-[20px]">check_circle</span>Connected · ' + count + ' ' + label;
  }}

  function setAzLoadState(state) {{
    const btn = document.getElementById("rc-az-load-dbs");
    if (!btn) return;
    if (azFailTimer) {{
      clearTimeout(azFailTimer);
      azFailTimer = null;
    }}
    if (state === "loading") {{
      btn.disabled = true;
      btn.className = DB2_BTN_TESTING;
      btn.innerHTML = '<span class="material-symbols-outlined text-[20px] animate-spin">refresh</span>Connecting…';
      return;
    }}
    if (state === "verified") {{
      btn.disabled = false;
      btn.className = DB2_BTN_SUCCESS;
      btn.innerHTML = azSuccessHtml(azLoadedCount);
      return;
    }}
    if (state === "failed") {{
      btn.disabled = false;
      btn.className = DB2_BTN_FAILED;
      btn.innerHTML = azIdleHtml();
      azFailTimer = setTimeout(function () {{ setAzLoadState("idle"); }}, 2500);
      return;
    }}
    btn.disabled = false;
    btn.className = DB2_BTN_IDLE;
    btn.innerHTML = azIdleHtml();
  }}

  function onAzConnectionFieldChange() {{
    if (azVerifiedSnapshot !== null && azVerifiedSnapshot !== azConnectionFingerprint()) {{
      azVerifiedSnapshot = null;
      azLoadedCount = 0;
      setAzLoadState("idle");
    }}
  }}

  function db2Fingerprint() {{
    const d = collectDb2();
    return JSON.stringify([d.database, d.host, d.port, d.username, d.password]);
  }}

  function db2IdleHtml() {{
    return '<span class="material-symbols-outlined text-[20px]">check_circle</span>Test Connection';
  }}

  function db2SuccessHtml() {{
    return '<span class="material-symbols-outlined text-[20px]">check_circle</span>Connection successful';
  }}

  function setDb2TestState(state) {{
    const btn = document.getElementById("rc-db2-test");
    if (!btn) return;
    if (db2FailTimer) {{
      clearTimeout(db2FailTimer);
      db2FailTimer = null;
    }}
    if (state === "testing") {{
      btn.disabled = true;
      btn.className = DB2_BTN_TESTING;
      btn.innerHTML = "Testing…";
      return;
    }}
    if (state === "verified") {{
      btn.disabled = false;
      btn.className = DB2_BTN_SUCCESS;
      btn.innerHTML = db2SuccessHtml();
      return;
    }}
    if (state === "failed") {{
      btn.disabled = false;
      btn.className = DB2_BTN_FAILED;
      btn.innerHTML = db2IdleHtml();
      db2FailTimer = setTimeout(function () {{ setDb2TestState("idle"); }}, 2500);
      return;
    }}
    btn.disabled = false;
    btn.className = DB2_BTN_IDLE;
    btn.innerHTML = db2IdleHtml();
  }}

  function onDb2FieldChange() {{
    if (db2VerifiedSnapshot !== null && db2VerifiedSnapshot !== db2Fingerprint()) {{
      db2VerifiedSnapshot = null;
      setDb2TestState("idle");
    }}
  }}

  async function testDb2() {{
    setDb2TestState("testing");
    try {{
      const payload = await postJson(TEST_DB2_URL, collectDb2());
      if (payload.ok) {{
        db2VerifiedSnapshot = db2Fingerprint();
        setDb2TestState("verified");
        toast(payload.message || "DB2 connection OK.", false);
      }} else {{
        db2VerifiedSnapshot = null;
        setDb2TestState("failed");
        toast(payload.error || payload.message || "Test failed.", true);
      }}
    }} catch (err) {{
      db2VerifiedSnapshot = null;
      setDb2TestState("failed");
      toast(err.message || "DB2 test request failed.", true);
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
    const sid = rcSessionId();
    const compareBtn = document.getElementById("rc-compare-btn");
    if (compareBtn) {{
      compareBtn.disabled = true;
      compareBtn.classList.add("opacity-70", "cursor-wait");
    }}
    postJson(SAVE_CONNECT_URL, {{
      rc_sid: sid,
      rc_token: rcSessionToken(),
      database: db2.database,
      host: db2.host,
      port: db2.port || "50000",
      username: db2.username,
      password: db2.password,
      server: az.server,
      az_database: az.database,
      auth_method: az.auth_method,
      trust_server_certificate: az.trust_server_certificate,
    }}).then(function (payload) {{
      if (compareBtn) {{
        compareBtn.disabled = false;
        compareBtn.classList.remove("opacity-70", "cursor-wait");
      }}
      if (!payload.ok) {{
        toast(payload.error || payload.message || "Could not save credentials.", true);
        return;
      }}
      if (payload.rc_token) {{
        setRcSessionToken(payload.rc_token);
      }}
      const params = new URLSearchParams();
      params.set("rc_action", "connect");
      if (payload.rc_bind) {{
        params.set("rc_bind", payload.rc_bind);
      }}
      rcNavigate(params);
    }}).catch(function (err) {{
      if (compareBtn) {{
        compareBtn.disabled = false;
        compareBtn.classList.remove("opacity-70", "cursor-wait");
      }}
      toast(err.message || "Connect request failed.", true);
    }});
  }}

  function wireSetup() {{
    const db2Test = document.getElementById("rc-db2-test");
    if (db2Test) db2Test.addEventListener("click", function (e) {{ e.preventDefault(); testDb2(); }});
    DB2_FIELD_IDS.forEach(function (id) {{
      const el = document.getElementById(id);
      if (el) el.addEventListener("input", onDb2FieldChange);
    }});
    setDb2TestState("idle");
    const azLoad = document.getElementById("rc-az-load-dbs");
    if (azLoad) azLoad.addEventListener("click", function (e) {{ e.preventDefault(); loadAzureDatabases(); }});
    const azServer = document.getElementById("rc-az-server");
    if (azServer) azServer.addEventListener("input", onAzConnectionFieldChange);
    document.querySelectorAll('input[name="auth_type_modal"]').forEach(function (el) {{
      el.addEventListener("change", onAzConnectionFieldChange);
    }});
    const azTrust = document.getElementById("rc-az-trust-cert");
    if (azTrust) azTrust.addEventListener("change", onAzConnectionFieldChange);
    setAzLoadState("idle");
    {f'''if ({json.dumps(bool(view.az_database_options))} && !EDIT_MODE) {{
      azVerifiedSnapshot = azConnectionFingerprint();
      azLoadedCount = {len(view.az_database_options)};
      setAzLoadState("verified");
    }}''' if view.az_database_options else ''}
    if (EDIT_MODE) {{
      const server = (document.getElementById("rc-az-server") || {{ value: "" }}).value.trim();
      if (server) loadAzureDatabases();
    }}
    const compareBtn = document.getElementById("rc-compare-btn");
    if (compareBtn) compareBtn.addEventListener("click", function (e) {{ e.preventDefault(); connectAndCompare(); }});
    const closeBtn = document.getElementById("rc-close-btn");
    if (closeBtn) closeBtn.addEventListener("click", function (e) {{
      e.preventDefault();
      if (EDIT_MODE) navigateBackToWorkspace();
      else navigateHomeClear();
    }});
  }}

  wireSetup();
  {f'toast({_js_literal(view.toast_message)}, {json.dumps(view.toast_error)});' if view.toast_message else ''}
}})();
</script>
<div id="rc-toast" style="display:none"></div>
"""


def _wire_rc_setup_document(source: str, view: RowCompareSetupView) -> str:
    doc = source
    close_btn = (
        '<button aria-label="Close modal" id="rc-close-btn" type="button" '
        'class="w-10 h-10 flex items-center justify-center rounded-full '
        'hover:bg-surface-container-high transition-colors text-outline">'
        '<span class="material-symbols-outlined">close</span></button>'
    )
    back_btn = (
        '<button aria-label="Back to workspace" id="rc-close-btn" type="button" '
        'class="flex items-center gap-1 text-on-secondary-container hover:text-primary '
        'transition-colors text-sm font-medium">'
        '<span class="material-symbols-outlined text-sm">arrow_back</span>Back</button>'
    )
    default_close = (
        '<button aria-label="Close modal" id="rc-close-btn" class="w-10 h-10 flex items-center '
        'justify-center rounded-full hover:bg-surface-container-high transition-colors text-outline">\n'
        '<span class="material-symbols-outlined">close</span>\n</button>'
    )
    if view.edit_mode:
        doc = doc.replace(default_close, back_btn, 1)
    else:
        doc = doc.replace(default_close, close_btn, 1)
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
    doc = _regex_inject(
        _RC_AZ_SERVER_MICRO,
        _az_server_input_html(view.az_server),
        doc,
        count=1,
    )
    doc = _RC_AZ_DATABASE_MICRO.sub(
        lambda m: m.group(1)
        + _azure_database_options_html(view.az_database, view.az_database_options)
        + m.group(2),
        doc,
        count=1,
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
    doc = _regex_inject(_RC_SETUP_MICRO, _rc_setup_bridge_script(view), doc, count=1)
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


def _rc_workspace_bridge_script(view: RowCompareWorkspaceView) -> str:
    run_compare_url = rc_run_comparison_api_url()
    create_bind_url = rc_create_bind_api_url()
    initial_views = json.dumps(view.result_tbody_views) if view.result_tbody_views else "null"
    return f"""
<script>
(function () {{
  const RC_PAGE = {json.dumps(ROW_COMPARE_PAGE)};
  const HOME_CLEAR_URL = {json.dumps(_HOME_CLEAR_URL)};
  const RUN_COMPARE_URL = {json.dumps(run_compare_url)};
  const CREATE_BIND_URL = {json.dumps(create_bind_url)};
  const RC_SID_KEY = "rc_sid";
  const RC_TOKEN_KEY = "rc_token";
  const FILTER_ACTIVE =
    "h-10 px-md text-body-sm font-bold text-primary border-b-2 border-primary transition-all";
  const FILTER_IDLE =
    "h-10 px-md text-body-sm font-medium text-secondary hover:bg-surface-container-high hover:text-on-surface transition-all";
  let runInFlight = false;
  let lastComparisonViews = {initial_views};
  let currentFilter = "all";

  function rcSessionToken() {{
    try {{
      return sessionStorage.getItem(RC_TOKEN_KEY) || "";
    }} catch (err) {{
      return "";
    }}
  }}

  (function syncServerSession() {{
    var sid = {_js_literal(view.rc_sid)};
    var token = {_js_literal(view.rc_token)};
    if (sid) sessionStorage.setItem(RC_SID_KEY, sid);
    if (token) sessionStorage.setItem(RC_TOKEN_KEY, token);
  }})();

  function rcSessionId() {{
    try {{
      let sid = sessionStorage.getItem(RC_SID_KEY);
      if (!sid) {{
        sid = (window.crypto && window.crypto.randomUUID)
          ? window.crypto.randomUUID()
          : "rc-" + Date.now() + "-" + Math.random().toString(16).slice(2);
        sessionStorage.setItem(RC_SID_KEY, sid);
      }}
      return sid;
    }} catch (err) {{
      return "rc-" + Date.now();
    }}
  }}

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
    el.className = "fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] px-lg py-sm rounded shadow-lg text-body-sm "
      + (isError ? "bg-error-container text-on-error-container" : "bg-primary text-on-primary");
    el.style.display = "block";
    setTimeout(function () {{ el.style.display = "none"; }}, 5000);
  }}

  function setText(id, text) {{
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }}

  function setActiveFilter(filter) {{
    const buttons = {{
      all: document.getElementById("rc-filter-all"),
      mismatch: document.getElementById("rc-filter-mismatch"),
      match: document.getElementById("rc-filter-match"),
      failed: document.getElementById("rc-filter-failed"),
    }};
    Object.keys(buttons).forEach(function (key) {{
      const btn = buttons[key];
      if (btn) btn.className = key === filter ? FILTER_ACTIVE : FILTER_IDLE;
    }});
  }}

  function applyResultFilter(filter) {{
    if (!lastComparisonViews) return;
    currentFilter = filter;
    setActiveFilter(filter);
    const tbody = document.getElementById("rc-results-tbody");
    if (!tbody) return;
    tbody.innerHTML = lastComparisonViews[filter] || lastComparisonViews.all || "";
    if (typeof window.syncRcFrameHeight === "function") window.syncRcFrameHeight();
  }}

  function applyComparisonResults(payload) {{
    const m = payload.metrics || {{}};
    setText("rc-metric-total", String(m.tables_source ?? 0));
    setText("rc-metric-matches", String(m.matched ?? 0));
    setText("rc-metric-mismatches", String(m.mismatched ?? 0));
    setText("rc-metric-failed", String(m.missing ?? 0));
    setText("rc-metric-rows", String(m.rows_label ?? "—"));
    lastComparisonViews = payload.tbody_views || {{
      all: payload.tbody_html || "",
    }};
    applyResultFilter(currentFilter);
  }}

  function wireResultFilters() {{
    const filters = [
      ["rc-filter-all", "all"],
      ["rc-filter-mismatch", "mismatch"],
      ["rc-filter-match", "match"],
      ["rc-filter-failed", "failed"],
    ];
    filters.forEach(function (pair) {{
      const btn = document.getElementById(pair[0]);
      if (!btn) return;
      btn.addEventListener("click", function (e) {{
        e.preventDefault();
        applyResultFilter(pair[1]);
      }});
    }});
    setActiveFilter(currentFilter);
  }}

  function runCompareFallback(mode) {{
    const p = new URLSearchParams();
    p.set("rc_action", "run");
    p.set("cmp_target_table_mode", mode);
    rcNavigate(p);
  }}

  async function runComparison() {{
    if (runInFlight) return;
    const runBtn = document.getElementById("rc-run-btn");
    const originalHtml = runBtn ? runBtn.innerHTML : "";
    const staging = document.querySelector('input[name="table_type"][value="staging"]');
    const mode = staging && staging.checked ? "staging" : "original";
    runInFlight = true;
    if (runBtn) {{
      runBtn.disabled = true;
      runBtn.innerHTML =
        '<span class="material-symbols-outlined animate-spin">sync</span> RUNNING...';
    }}
    try {{
      const response = await fetch(apiUrl(RUN_COMPARE_URL), {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          rc_sid: rcSessionId(),
          rc_token: rcSessionToken(),
          target_table_mode: mode,
        }}),
      }});
      const contentType = (response.headers.get("content-type") || "").toLowerCase();
      if (!contentType.includes("application/json")) {{
        toast("Comparison API unavailable — reloading with server run.", true);
        runCompareFallback(mode);
        return;
      }}
      let payload = {{ ok: false, error: "Comparison failed." }};
      try {{
        payload = await response.json();
      }} catch (parseErr) {{
        toast("Comparison API unavailable — reloading with server run.", true);
        runCompareFallback(mode);
        return;
      }}
      if (!response.ok || !payload.ok) {{
        toast(payload.error || ("Comparison failed (HTTP " + response.status + ")."), true);
        return;
      }}
      applyComparisonResults(payload);
      toast(payload.message || "Comparison complete.", false);
    }} catch (err) {{
      toast(err.message || "Comparison request failed.", true);
    }} finally {{
      runInFlight = false;
      if (runBtn) {{
        runBtn.disabled = false;
        runBtn.innerHTML = originalHtml ||
          '<span class="material-symbols-outlined">play_arrow</span> RUN COMPARISON';
      }}
    }}
  }}

  const homeBtn = document.getElementById("rc-home-back");
  if (homeBtn) homeBtn.addEventListener("click", function (e) {{
    e.preventDefault();
    window.parent.postMessage({{ type: "stitch-oe-nav", url: HOME_CLEAR_URL }}, "*");
    try {{ window.top.location.href = HOME_CLEAR_URL; }} catch (err) {{}}
  }});

  const editBtn = document.getElementById("rc-edit-creds");
  if (editBtn) editBtn.addEventListener("click", function (e) {{
    e.preventDefault();
    const sid = rcSessionId();
    const token = rcSessionToken();
    if (!sid || !token) {{
      toast("Session expired — connect again from setup.", true);
      return;
    }}
    editBtn.disabled = true;
    fetch(apiUrl(CREATE_BIND_URL), {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ rc_sid: sid, rc_token: token }}),
    }}).then(function (res) {{
      return res.json().then(function (payload) {{
        return {{ res: res, payload: payload }};
      }});
    }}).then(function (out) {{
      editBtn.disabled = false;
      if (!out.res.ok || !out.payload.ok || !out.payload.rc_bind) {{
        toast(out.payload.error || "Could not open edit.", true);
        return;
      }}
      const p = new URLSearchParams();
      p.set("rc_action", "edit");
      p.set("rc_bind", out.payload.rc_bind);
      rcNavigate(p);
    }}).catch(function (err) {{
      editBtn.disabled = false;
      toast(err.message || "Edit request failed.", true);
    }});
  }});

  const runBtn = document.getElementById("rc-run-btn");
  if (runBtn) runBtn.addEventListener("click", function (e) {{
    e.preventDefault();
    runComparison();
  }});

  wireResultFilters();
  if (lastComparisonViews) {{
    applyResultFilter(currentFilter);
  }}

  {f'toast({_js_literal(view.toast_message)}, {json.dumps(view.toast_error)});' if view.toast_message else ''}
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

    metric_ids = [
        (
            '<p class="text-label-caps text-secondary">TOTAL TABLES</p>\n<p class="font-headline-md text-headline-md font-bold">',
            '<p class="text-label-caps text-secondary">TOTAL TABLES</p>\n<p id="rc-metric-total" class="font-headline-md text-headline-md font-bold">',
        ),
        (
            '<p class="text-label-caps text-secondary">MATCHES</p>\n<p class="font-headline-md text-headline-md font-bold text-emerald-700">',
            '<p class="text-label-caps text-secondary">MATCHES</p>\n<p id="rc-metric-matches" class="font-headline-md text-headline-md font-bold text-emerald-700">',
        ),
        (
            '<p class="text-label-caps text-secondary">MISMATCHES</p>\n<p class="font-headline-md text-headline-md font-bold text-amber-700">',
            '<p class="text-label-caps text-secondary">MISMATCHES</p>\n<p id="rc-metric-mismatches" class="font-headline-md text-headline-md font-bold text-amber-700">',
        ),
        (
            '<p class="text-label-caps text-secondary">FAILED</p>\n<p class="font-headline-md text-headline-md font-bold text-red-700">',
            '<p class="text-label-caps text-secondary">FAILED</p>\n<p id="rc-metric-failed" class="font-headline-md text-headline-md font-bold text-red-700">',
        ),
        (
            '<p class="text-label-caps text-secondary">ROWS SCANNED</p>\n<p class="font-headline-md text-headline-md font-bold">',
            '<p class="text-label-caps text-secondary">ROWS SCANNED</p>\n<p id="rc-metric-rows" class="font-headline-md text-headline-md font-bold">',
        ),
    ]
    for old, new in metric_ids:
        doc = doc.replace(old, new, 1)

    doc = _regex_inject(
        _TBODY_MICRO,
        f'<tbody id="rc-results-tbody" class="font-body-sm text-body-sm divide-y divide-outline-variant">{view.result_rows_html}</tbody>',
        doc,
        count=1,
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
    doc = _regex_inject(_RC_WORKSPACE_MICRO, _rc_workspace_bridge_script(view), doc, count=1)
    doc = doc.replace("</body>", _WORKSPACE_FRAME_HEIGHT_SCRIPT + "</body>")
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
    from db2_explorer.ui import stitch_shell as _shell

    _shell._HTML_CACHE.pop("row_workspace", None)
    doc = _wire_rc_workspace_document(_read_html("row_workspace"), view)
    st.markdown(
        f"<style>{shell_iframe_css()}{_RC_WORKSPACE_SHELL_CSS}</style>",
        unsafe_allow_html=True,
    )
    components.html(doc, height=900, scrolling=False)
