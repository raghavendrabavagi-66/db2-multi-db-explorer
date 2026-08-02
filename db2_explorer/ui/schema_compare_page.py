"""Schema Compare stitch pages — setup (06) and workspace (07)."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from db2_explorer.api.register import (
    sc_create_bind_api_url,
    sc_list_azure_databases_api_url,
    sc_list_branches_api_url,
    sc_list_db_folders_api_url,
    sc_list_server_folders_api_url,
    sc_load_deployment_api_url,
    sc_run_comparison_api_url,
    sc_save_connect_api_url,
)
from db2_explorer.gitlab.client import gitlab_repo_display
from db2_explorer.ui.sch_session import schema_compare_home_clear_url
from db2_explorer.ui.stitch_shell import (
    _read_html,
    inject_shell_component,
    shell_iframe_css,
)

SCHEMA_COMPARE_PAGE = "/Schema_Compare"
_HOME_CLEAR_URL = schema_compare_home_clear_url()

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
  function syncScFrameHeight() {
    var h = parentViewportHeight();
    window.parent.postMessage({ type: "streamlit:setFrameHeight", height: h }, "*");
  }
  window.syncScFrameHeight = syncScFrameHeight;
  syncScFrameHeight();
  window.addEventListener("load", syncScFrameHeight);
  window.addEventListener("resize", syncScFrameHeight);
  try {
    window.parent.addEventListener("resize", syncScFrameHeight);
  } catch (err) {}
})();
</script>
"""

_SC_WORKSPACE_SHELL_CSS = """
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

_SC_SETUP_MICRO = re.compile(
    r'<script id="sc-setup-bridge-placeholder"></script>',
    re.DOTALL,
)

_SC_WORKSPACE_MICRO = re.compile(
    r'<script id="sc-workspace-bridge-placeholder"></script>',
    re.DOTALL,
)

_SC_TBODY_MICRO = re.compile(
    r'<tbody id="sc-results-tbody" class="text-body-sm">.*?</tbody>',
    re.DOTALL,
)

_SC_CLOSE_BTN_MICRO = re.compile(
    r'<button aria-label="Close modal" id="sc-close-btn"[^>]*>\s*'
    r'<span class="material-symbols-outlined[^"]*">close</span>\s*</button>',
    re.DOTALL,
)


def _js_literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _regex_inject(pattern: re.Pattern[str], repl: str, doc: str, *, count: int = 0) -> str:
    return pattern.sub(lambda _match: repl, doc, count=count)


def _auth_entra_checked(auth: str) -> str:
    return "checked" if auth != "windows" else ""


def _auth_windows_checked(auth: str) -> str:
    return "checked" if auth == "windows" else ""


def _gitlab_repo_label_html() -> str:
    base_url, project_id = gitlab_repo_display()
    return (
        f'<a href="{html.escape(base_url)}" class="text-primary hover:underline">'
        f'{html.escape(base_url)}</a><span class="text-outline">·</span>'
        f'<span class="text-on-surface">project {html.escape(project_id)}</span>'
    )


@dataclass
class SchemaCompareSetupView:
    gitlab_token: str = ""
    branch: str = ""
    branch_list: list[str] = field(default_factory=list)
    database: str = ""
    db_folder_list: list[str] = field(default_factory=list)
    server: str = ""
    server_folder_list: list[str] = field(default_factory=list)
    az_server: str = ""
    az_database: str = ""
    az_database_options: list[str] = field(default_factory=list)
    az_auth: str = "entra"
    az_trust_cert: bool = True
    deployment_loaded: bool = False
    bundle_path: str = ""
    deployment_files: dict[str, str] = field(default_factory=dict)
    missing_files: list[str] = field(default_factory=list)
    edit_mode: bool = False
    sch_sid: str = ""
    sch_token: str = ""
    toast_message: str = ""
    toast_error: bool = False


@dataclass
class SchemaCompareWorkspaceView:
    source_label: str = "GitLab Source"
    target_label: str = "Azure SQL Target"
    summary: dict[str, Any] = field(default_factory=dict)
    table_html: str = ""
    objects: dict[str, dict[str, Any]] = field(default_factory=dict)
    selected_object_key: str = ""
    has_results: bool = False
    sch_sid: str = ""
    sch_token: str = ""
    toast_message: str = ""
    toast_error: bool = False


def _sc_setup_bridge_script(view: SchemaCompareSetupView) -> str:
    return f"""
<script>
(function () {{
  const SC_PAGE = {json.dumps(SCHEMA_COMPARE_PAGE)};
  const HOME_CLEAR_URL = {json.dumps(_HOME_CLEAR_URL)};
  const LIST_BRANCHES_URL = {json.dumps(sc_list_branches_api_url())};
  const LIST_DB_FOLDERS_URL = {json.dumps(sc_list_db_folders_api_url())};
  const LIST_SERVER_FOLDERS_URL = {json.dumps(sc_list_server_folders_api_url())};
  const LOAD_DEPLOYMENT_URL = {json.dumps(sc_load_deployment_api_url())};
  const LIST_AZ_URL = {json.dumps(sc_list_azure_databases_api_url())};
  const SAVE_CONNECT_URL = {json.dumps(sc_save_connect_api_url())};
  const CREATE_BIND_URL = {json.dumps(sc_create_bind_api_url())};
  const SC_SID_KEY = "sch_sid";
  const SC_TOKEN_KEY = "sch_token";
  const EDIT_MODE = {json.dumps(view.edit_mode)};

  let branchList = {_js_literal(view.branch_list)};
  let dbFolderList = {_js_literal(view.db_folder_list)};
  let serverFolderList = {_js_literal(view.server_folder_list)};
  let azDatabaseOptions = {_js_literal(view.az_database_options)};
  let deploymentFiles = {_js_literal(view.deployment_files)};
  let missingFiles = {_js_literal(view.missing_files)};
  let bundlePath = {_js_literal(view.bundle_path)};
  let deploymentLoaded = {json.dumps(view.deployment_loaded or bool(view.deployment_files))};

  function scSessionToken() {{
    try {{ return sessionStorage.getItem(SC_TOKEN_KEY) || ""; }} catch (err) {{ return ""; }}
  }}
  function setScSessionToken(token) {{
    try {{ if (token) sessionStorage.setItem(SC_TOKEN_KEY, token); }} catch (err) {{}}
  }}
  (function syncServerSession() {{
    var sid = {_js_literal(view.sch_sid)};
    var token = {_js_literal(view.sch_token)};
    if (sid) sessionStorage.setItem(SC_SID_KEY, sid);
    if (token) setScSessionToken(token);
  }})();

  function scSessionId() {{
    try {{
      let sid = sessionStorage.getItem(SC_SID_KEY);
      if (!sid) {{
        sid = (window.crypto && window.crypto.randomUUID)
          ? window.crypto.randomUUID()
          : "sc-" + Date.now() + "-" + Math.random().toString(16).slice(2);
        sessionStorage.setItem(SC_SID_KEY, sid);
      }}
      return sid;
    }} catch (err) {{ return "sc-" + Date.now(); }}
  }}

  function apiUrl(pathOrFull) {{
    if (pathOrFull.startsWith("http")) return pathOrFull;
    try {{
      const origin = window.top.location.origin;
      if (origin && origin !== "null") return origin + pathOrFull;
    }} catch (err) {{}}
    return pathOrFull;
  }}

  function scPagePath() {{
    try {{
      const topPath = window.top.location.pathname || "";
      if (topPath.indexOf("Schema_Compare") >= 0) return topPath;
    }} catch (err) {{}}
    return SC_PAGE;
  }}

  function scNavigate(params) {{
    const url = scPagePath() + "?" + params.toString();
    window.parent.postMessage({{ type: "stitch-oe-nav", url: url }}, "*");
    try {{ window.top.location.href = url; }} catch (err) {{}}
  }}

  function toast(msg, isError) {{
    const el = document.getElementById("sc-toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] px-lg py-sm rounded shadow-lg text-body-sm font-medium "
      + (isError ? "bg-error-container text-on-error-container" : "bg-primary text-on-primary");
    el.style.display = "block";
    setTimeout(function () {{ el.style.display = "none"; }}, 5000);
  }}

  function postJson(url, body) {{
    return fetch(apiUrl(url), {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify(body),
    }}).then(function (res) {{
      return res.json().then(function (payload) {{
        return {{ res: res, payload: payload }};
      }});
    }});
  }}

  function comboboxSetValue(inputId, value) {{
    const input = document.getElementById(inputId);
    if (input) input.value = value || "";
  }}

  function comboboxFilteredOptions(all, query) {{
    const q = (query || "").trim().toLowerCase();
    if (!q) return all.slice();
    return all.filter(function (name) {{
      return String(name).toLowerCase().indexOf(q) >= 0;
    }});
  }}

  function createCombobox(config) {{
    const input = document.getElementById(config.inputId);
    const list = document.getElementById(config.listId);
    if (!input || !list) return null;

    const state = {{
      input: input,
      list: list,
      getOptions: config.getOptions,
      onSelect: config.onSelect || null,
      highlight: -1,
    }};

    function optionButtons() {{
      return list.querySelectorAll(".sc-combobox-option");
    }}

    function setHighlight(index) {{
      const buttons = optionButtons();
      state.highlight = index;
      buttons.forEach(function (btn, i) {{
        btn.classList.toggle("sc-combobox-active", i === index);
      }});
      if (index >= 0 && buttons[index]) {{
        buttons[index].scrollIntoView({{ block: "nearest" }});
      }}
    }}

    function hideList() {{
      list.classList.add("hidden");
      state.highlight = -1;
    }}

    function pick(name) {{
      input.value = name;
      hideList();
      if (state.onSelect) state.onSelect(name);
    }}

    function renderList(filterQuery) {{
      const query = filterQuery !== undefined ? filterQuery : input.value;
      const items = comboboxFilteredOptions(state.getOptions() || [], query);
      list.innerHTML = "";
      if (!items.length) {{
        list.innerHTML = '<div class="px-md py-2 text-body-sm text-secondary">No matches</div>';
        list.classList.remove("hidden");
        return;
      }}
      items.forEach(function (name) {{
        const row = document.createElement("button");
        row.type = "button";
        row.className = "sc-combobox-option block w-full text-left px-md py-2 text-body-sm text-on-surface hover:bg-surface-container-low border-0 bg-transparent cursor-pointer";
        row.textContent = name;
        row.addEventListener("mousedown", function (ev) {{
          ev.preventDefault();
          pick(name);
        }});
        list.appendChild(row);
      }});
      list.classList.remove("hidden");
      setHighlight(-1);
    }}

    input.addEventListener("focus", function () {{
      renderList("");
      input.select();
    }});
    input.addEventListener("input", function () {{
      renderList();
    }});
    input.addEventListener("keydown", function (ev) {{
      const buttons = optionButtons();
      if (ev.key === "ArrowDown") {{
        ev.preventDefault();
        if (list.classList.contains("hidden")) renderList();
        const next = buttons.length ? Math.min(state.highlight + 1, buttons.length - 1) : -1;
        setHighlight(next);
      }} else if (ev.key === "ArrowUp") {{
        ev.preventDefault();
        const prev = buttons.length ? Math.max(state.highlight - 1, 0) : -1;
        setHighlight(prev);
      }} else if (ev.key === "Enter") {{
        if (state.highlight >= 0 && buttons[state.highlight]) {{
          ev.preventDefault();
          pick(buttons[state.highlight].textContent || "");
        }}
      }} else if (ev.key === "Escape") {{
        hideList();
      }}
    }});
    input.addEventListener("blur", function () {{
      setTimeout(hideList, 120);
    }});

    return state;
  }}

  function collectAzure() {{
    const authEl = document.querySelector('input[name="auth_type_modal"]:checked');
    return {{
      server: (document.getElementById("sc-az-server") || {{ value: "" }}).value.trim(),
      database: (document.getElementById("sc-az-database") || {{ value: "" }}).value.trim(),
      auth_method: authEl ? authEl.value : "entra",
      trust_server_certificate: !!(document.getElementById("sc-az-trust-cert") || {{}}).checked,
    }};
  }}

  const DEPLOY_BTN_BASE = "h-9 px-md font-label-caps text-label-caps flex items-center gap-xs transition-colors rounded";
  const DEPLOY_BTN_IDLE = DEPLOY_BTN_BASE + " border border-outline-variant bg-surface-container-low text-on-surface hover:bg-surface-container-high";
  const DEPLOY_BTN_SUCCESS = DEPLOY_BTN_BASE + " bg-emerald-600 text-white border border-emerald-600 hover:brightness-110";
  const DEPLOY_BTN_FAILED = DEPLOY_BTN_BASE + " border border-red-600 text-red-700 bg-red-50";
  const DEPLOY_BTN_LOADING = DEPLOY_BTN_BASE + " border border-outline-variant bg-surface-container-low text-on-surface opacity-70 cursor-wait";
  const SC_GITLAB_SOURCE_IDS = ["sc-gitlab-token", "sc-branch", "sc-database", "sc-server"];

  let deployVerifiedSnapshot = null;
  let deployFailTimer = null;

  function deployIdleHtml() {{
    return '<span class="material-symbols-outlined text-[18px]">folder_open</span>Load Deployment';
  }}

  function deploySuccessHtml() {{
    return '<span class="material-symbols-outlined text-[18px]">check_circle</span>Loaded';
  }}

  function deployFingerprint() {{
    return JSON.stringify([
      (document.getElementById("sc-gitlab-token") || {{ value: "" }}).value.trim(),
      (document.getElementById("sc-branch") || {{ value: "" }}).value.trim(),
      (document.getElementById("sc-database") || {{ value: "" }}).value.trim(),
      (document.getElementById("sc-server") || {{ value: "" }}).value.trim(),
    ]);
  }}

  function setGitLabFieldsDirty(dirty) {{
    SC_GITLAB_SOURCE_IDS.forEach(function (id) {{
      const el = document.getElementById(id);
      if (!el) return;
      el.classList.toggle("border-amber-500", dirty);
      el.classList.toggle("ring-1", dirty);
      el.classList.toggle("ring-amber-200", dirty);
    }});
  }}

  function clearDeploymentCache() {{
    deploymentFiles = {{}};
    missingFiles = [];
    bundlePath = "";
    deploymentLoaded = false;
  }}

  function setDeployLoadState(state) {{
    const btn = document.getElementById("sc-load-deployment");
    if (!btn) return;
    if (deployFailTimer) {{
      clearTimeout(deployFailTimer);
      deployFailTimer = null;
    }}
    if (state === "loading") {{
      btn.disabled = true;
      btn.className = DEPLOY_BTN_LOADING;
      btn.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">refresh</span>Loading…';
      return;
    }}
    if (state === "loaded") {{
      btn.disabled = false;
      btn.className = DEPLOY_BTN_SUCCESS;
      btn.innerHTML = deploySuccessHtml();
      setGitLabFieldsDirty(false);
      return;
    }}
    if (state === "failed") {{
      btn.disabled = false;
      btn.className = DEPLOY_BTN_FAILED;
      btn.innerHTML = deployIdleHtml();
      deployFailTimer = setTimeout(function () {{ setDeployLoadState("idle"); }}, 10000);
      return;
    }}
    btn.disabled = false;
    btn.className = DEPLOY_BTN_IDLE;
    btn.innerHTML = deployIdleHtml();
  }}

  function onGitLabSourceChange() {{
    if (deployVerifiedSnapshot !== null && deployVerifiedSnapshot !== deployFingerprint()) {{
      deployVerifiedSnapshot = null;
      clearDeploymentCache();
      setDeployLoadState("idle");
      setGitLabFieldsDirty(true);
    }}
  }}

  async function loadBranches() {{
    const token = (document.getElementById("sc-gitlab-token") || {{ value: "" }}).value.trim();
    if (!token) {{ toast("Enter GitLab token first.", true); return; }}
    const btn = document.getElementById("sc-branch-refresh");
    if (btn) btn.disabled = true;
    try {{
      const out = await postJson(LIST_BRANCHES_URL, {{ gitlab_token: token }});
      if (!out.res.ok || !out.payload.ok) {{
        toast(out.payload.error || "Failed to load branches.", true);
        return;
      }}
      branchList = out.payload.branches || [];
      comboboxSetValue("sc-branch", branchList[0] || "");
      onGitLabSourceChange();
      toast(out.payload.message || "Branches loaded.", false);
      await loadDbFolders();
    }} catch (err) {{
      toast(err.message || "Branch request failed.", true);
    }} finally {{
      if (btn) btn.disabled = false;
    }}
  }}

  async function loadDbFolders() {{
    const token = (document.getElementById("sc-gitlab-token") || {{ value: "" }}).value.trim();
    const branch = (document.getElementById("sc-branch") || {{ value: "" }}).value.trim();
    if (!token || !branch) return;
    const out = await postJson(LIST_DB_FOLDERS_URL, {{ gitlab_token: token, branch: branch }});
    if (!out.res.ok || !out.payload.ok) return;
    dbFolderList = out.payload.folders || [];
    comboboxSetValue("sc-database", "");
    comboboxSetValue("sc-server", "");
    serverFolderList = [];
    onGitLabSourceChange();
  }}

  async function loadServerFolders() {{
    const token = (document.getElementById("sc-gitlab-token") || {{ value: "" }}).value.trim();
    const branch = (document.getElementById("sc-branch") || {{ value: "" }}).value.trim();
    const database = (document.getElementById("sc-database") || {{ value: "" }}).value.trim();
    if (!token || !branch || !database) return;
    const out = await postJson(LIST_SERVER_FOLDERS_URL, {{
      gitlab_token: token, branch: branch, database: database,
    }});
    if (!out.res.ok || !out.payload.ok) return;
    serverFolderList = out.payload.folders || [];
    comboboxSetValue("sc-server", "");
    onGitLabSourceChange();
  }}

  async function loadDeployment() {{
    const token = (document.getElementById("sc-gitlab-token") || {{ value: "" }}).value.trim();
    const branch = (document.getElementById("sc-branch") || {{ value: "" }}).value.trim();
    const database = (document.getElementById("sc-database") || {{ value: "" }}).value.trim();
    const serverFolder = (document.getElementById("sc-server") || {{ value: "" }}).value.trim();
    if (!token || !branch || !database || !serverFolder) {{
      toast("Complete GitLab branch, database, and server folder.", true);
      return;
    }}
    setDeployLoadState("loading");
    try {{
      const out = await postJson(LOAD_DEPLOYMENT_URL, {{
        gitlab_token: token, branch: branch, database: database, server_folder: serverFolder,
      }});
      if (!out.res.ok || !out.payload.ok) {{
        deployVerifiedSnapshot = null;
        clearDeploymentCache();
        setDeployLoadState("failed");
        toast(out.payload.error || "Load deployment failed.", true);
        return;
      }}
      deploymentFiles = out.payload.deployment_files || {{}};
      missingFiles = out.payload.missing_files || [];
      bundlePath = out.payload.bundle_path || "";
      deploymentLoaded = Object.keys(deploymentFiles).length > 0;
      if (!deploymentLoaded) {{
        deployVerifiedSnapshot = null;
        setDeployLoadState("failed");
        toast("No deployment files found for this selection.", true);
        return;
      }}
      deployVerifiedSnapshot = deployFingerprint();
      setDeployLoadState("loaded");
      if (out.payload.target_server) {{
        const azServer = document.getElementById("sc-az-server");
        if (azServer) azServer.value = out.payload.target_server;
      }}
      if (out.payload.target_database) {{
        comboboxSetValue("sc-az-database", out.payload.target_database);
      }}
      toast(out.payload.message || "Deployment loaded.", false);
      if (missingFiles.length) {{
        toast("Missing in repo: " + missingFiles.join(", "), true);
      }}
    }} catch (err) {{
      deployVerifiedSnapshot = null;
      clearDeploymentCache();
      setDeployLoadState("failed");
      toast(err.message || "Load deployment failed.", true);
    }}
  }}

  async function loadAzureDatabases() {{
    const az = collectAzure();
    if (!az.server) {{ toast("Enter Azure server first.", true); return; }}
    const btn = document.getElementById("sc-az-load-dbs");
    if (btn) btn.disabled = true;
    try {{
      const out = await postJson(LIST_AZ_URL, az);
      if (!out.res.ok || !out.payload.ok) {{
        toast(out.payload.error || "Failed to list databases.", true);
        return;
      }}
      azDatabaseOptions = out.payload.databases || [];
      comboboxSetValue("sc-az-database", az.database || azDatabaseOptions[0] || "");
      toast(out.payload.message || "Databases loaded.", false);
    }} catch (err) {{
      toast(err.message || "Database list failed.", true);
    }} finally {{
      if (btn) btn.disabled = false;
    }}
  }}

  function compareNow() {{
    const token = (document.getElementById("sc-gitlab-token") || {{ value: "" }}).value.trim();
    const branch = (document.getElementById("sc-branch") || {{ value: "" }}).value.trim();
    const database = (document.getElementById("sc-database") || {{ value: "" }}).value.trim();
    const serverFolder = (document.getElementById("sc-server") || {{ value: "" }}).value.trim();
    const az = collectAzure();
    if (!token || !branch || !database || !serverFolder) {{
      toast("Complete all GitLab source fields.", true);
      return;
    }}
    if (!deploymentLoaded) {{
      toast("Load deployment before comparing.", true);
      return;
    }}
    if (!az.server || !az.database) {{
      toast("Complete Azure server and database.", true);
      return;
    }}
    const btn = document.getElementById("sc-compare-btn");
    if (btn) {{ btn.disabled = true; btn.classList.add("opacity-70"); }}
    postJson(SAVE_CONNECT_URL, {{
      sch_sid: scSessionId(),
      sch_token: scSessionToken(),
      gitlab_token: token,
      branch: branch,
      branch_list: branchList,
      database: database,
      db_folder_list: dbFolderList,
      server_folder: serverFolder,
      server_folder_list: serverFolderList,
      server: az.server,
      az_database: az.database,
      az_database_options: azDatabaseOptions,
      auth_method: az.auth_method,
      trust_server_certificate: az.trust_server_certificate,
      deployment_files: deploymentFiles,
      missing_files: missingFiles,
      bundle_path: bundlePath,
    }}).then(function (out) {{
      if (btn) {{ btn.disabled = false; btn.classList.remove("opacity-70"); }}
      if (!out.res.ok || !out.payload.ok) {{
        toast(out.payload.error || "Could not save credentials.", true);
        return;
      }}
      if (out.payload.sch_token) setScSessionToken(out.payload.sch_token);
      const p = new URLSearchParams();
      p.set("sch_action", "connect");
      if (out.payload.sch_bind) p.set("sch_bind", out.payload.sch_bind);
      scNavigate(p);
    }}).catch(function (err) {{
      if (btn) {{ btn.disabled = false; btn.classList.remove("opacity-70"); }}
      toast(err.message || "Compare request failed.", true);
    }});
  }}

  function navigateBackToWorkspace() {{
    const sid = scSessionId();
    const token = scSessionToken();
    if (!sid || !token) {{
      scNavigate(new URLSearchParams([["sch_action", "back"]]));
      return;
    }}
    postJson(CREATE_BIND_URL, {{ sch_sid: sid, sch_token: token }}).then(function (out) {{
      const p = new URLSearchParams();
      p.set("sch_action", "back");
      if (out.res && out.res.ok && out.payload.ok && out.payload.sch_bind) {{
        p.set("sch_bind", out.payload.sch_bind);
      }}
      scNavigate(p);
    }}).catch(function () {{
      scNavigate(new URLSearchParams([["sch_action", "back"]]));
    }});
  }}

  function navigateHomeClear() {{
    try {{
      sessionStorage.removeItem(SC_SID_KEY);
      sessionStorage.removeItem(SC_TOKEN_KEY);
    }} catch (err) {{}}
    window.parent.postMessage({{ type: "stitch-oe-nav", url: HOME_CLEAR_URL }}, "*");
    if (window.top && window.top !== window) {{
      window.top.postMessage({{ type: "stitch-oe-nav", url: HOME_CLEAR_URL }}, "*");
    }}
    try {{ window.top.location.href = HOME_CLEAR_URL; }} catch (err) {{}}
  }}

  createCombobox({{
    inputId: "sc-branch",
    listId: "sc-branch-list",
    getOptions: function () {{ return branchList; }},
    onSelect: function () {{ loadDbFolders(); onGitLabSourceChange(); }},
  }});
  createCombobox({{
    inputId: "sc-database",
    listId: "sc-database-list",
    getOptions: function () {{ return dbFolderList; }},
    onSelect: function () {{ loadServerFolders(); onGitLabSourceChange(); }},
  }});
  createCombobox({{
    inputId: "sc-server",
    listId: "sc-server-list",
    getOptions: function () {{ return serverFolderList; }},
    onSelect: function () {{ onGitLabSourceChange(); }},
  }});
  createCombobox({{
    inputId: "sc-az-database",
    listId: "sc-az-database-list",
    getOptions: function () {{ return azDatabaseOptions; }},
  }});

  comboboxSetValue("sc-branch", {_js_literal(view.branch)});
  comboboxSetValue("sc-database", {_js_literal(view.database)});
  comboboxSetValue("sc-server", {_js_literal(view.server)});
  comboboxSetValue("sc-az-database", {_js_literal(view.az_database)});

  SC_GITLAB_SOURCE_IDS.forEach(function (id) {{
    const el = document.getElementById(id);
    if (el) el.addEventListener("input", onGitLabSourceChange);
  }});

  if (deploymentLoaded) {{
    deployVerifiedSnapshot = deployFingerprint();
    setDeployLoadState("loaded");
  }} else {{
    setDeployLoadState("idle");
  }}

  if (EDIT_MODE) {{
    const azServer = (document.getElementById("sc-az-server") || {{ value: "" }}).value.trim();
    if (azServer) loadAzureDatabases();
  }}

  document.getElementById("sc-branch-refresh")?.addEventListener("click", function (e) {{
    e.preventDefault(); loadBranches();
  }});
  document.getElementById("sc-load-deployment")?.addEventListener("click", function (e) {{
    e.preventDefault(); loadDeployment();
  }});
  document.getElementById("sc-az-load-dbs")?.addEventListener("click", function (e) {{
    e.preventDefault(); loadAzureDatabases();
  }});
  document.getElementById("sc-compare-btn")?.addEventListener("click", function (e) {{
    e.preventDefault(); compareNow();
  }});
  document.getElementById("sc-close-btn")?.addEventListener("click", function (e) {{
    e.preventDefault();
    if (EDIT_MODE) navigateBackToWorkspace();
    else navigateHomeClear();
  }});

  {f'toast({_js_literal(view.toast_message)}, {json.dumps(view.toast_error)});' if view.toast_message else ''}
}})();
</script>
<div id="sc-toast" style="display:none"></div>
"""


def _sc_workspace_bridge_script(view: SchemaCompareWorkspaceView) -> str:
    objects_json = json.dumps(view.objects) if view.objects else "{}"
    return f"""
<script>
(function () {{
  const SC_PAGE = {json.dumps(SCHEMA_COMPARE_PAGE)};
  const HOME_CLEAR_URL = {json.dumps(_HOME_CLEAR_URL)};
  const RUN_COMPARE_URL = {json.dumps(sc_run_comparison_api_url())};
  const CREATE_BIND_URL = {json.dumps(sc_create_bind_api_url())};
  const SC_SID_KEY = "sch_sid";
  const SC_TOKEN_KEY = "sch_token";
  const SC_CACHE_KEY = "sch_comparison_cache";

  let objectMap = {objects_json};
  let selectedKey = {_js_literal(view.selected_object_key)};
  let activeTab = "sql";
  let compareInFlight = false;

  function scSessionToken() {{
    try {{ return sessionStorage.getItem(SC_TOKEN_KEY) || ""; }} catch (err) {{ return ""; }}
  }}

  function clearScBrowserSession() {{
    try {{
      sessionStorage.removeItem(SC_SID_KEY);
      sessionStorage.removeItem(SC_TOKEN_KEY);
      sessionStorage.removeItem(SC_CACHE_KEY);
    }} catch (err) {{}}
  }}

  function navigateHomeClear() {{
    clearScBrowserSession();
    window.parent.postMessage({{ type: "stitch-oe-nav", url: HOME_CLEAR_URL }}, "*");
    if (window.top && window.top !== window) {{
      window.top.postMessage({{ type: "stitch-oe-nav", url: HOME_CLEAR_URL }}, "*");
    }}
    try {{ window.top.location.href = HOME_CLEAR_URL; }} catch (err) {{}}
  }}

  (function syncServerSession() {{
    var sid = {_js_literal(view.sch_sid)};
    var token = {_js_literal(view.sch_token)};
    if (sid) sessionStorage.setItem(SC_SID_KEY, sid);
    if (token) sessionStorage.setItem(SC_TOKEN_KEY, token);
  }})();

  function scSessionId() {{
    try {{
      let sid = sessionStorage.getItem(SC_SID_KEY);
      if (!sid) {{
        sid = (window.crypto && window.crypto.randomUUID)
          ? window.crypto.randomUUID()
          : "sc-" + Date.now();
        sessionStorage.setItem(SC_SID_KEY, sid);
      }}
      return sid;
    }} catch (err) {{ return "sc-" + Date.now(); }}
  }}

  function apiUrl(pathOrFull) {{
    if (pathOrFull.startsWith("http")) return pathOrFull;
    try {{
      const origin = window.top.location.origin;
      if (origin && origin !== "null") return origin + pathOrFull;
    }} catch (err) {{}}
    return pathOrFull;
  }}

  function scNavigate(params) {{
    const url = SC_PAGE + "?" + params.toString();
    window.parent.postMessage({{ type: "stitch-oe-nav", url: url }}, "*");
    try {{ window.top.location.href = url; }} catch (err) {{}}
  }}

  function toast(msg, isError) {{
    const el = document.getElementById("sc-toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "fixed bottom-6 left-1/2 -translate-x-1/2 z-[200] px-lg py-sm rounded shadow-lg text-body-sm font-medium "
      + (isError ? "bg-error-container text-on-error-container" : "bg-primary text-on-primary");
    el.style.display = "block";
    setTimeout(function () {{ el.style.display = "none"; }}, 5000);
  }}

  function setText(id, text) {{
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }}

  function applyComparisonResults(payload) {{
    objectMap = payload.objects || {{}};
    if (payload.table_html) {{
      const tbody = document.getElementById("sc-results-tbody");
      if (tbody) tbody.innerHTML = payload.table_html;
    }}
    setText("sc-source-label", payload.source_label || "GitLab Source");
    setText("sc-target-label", payload.target_label || "Azure SQL Target");
    const total = payload.total_objects || payload.summary?.total || 0;
    setText("sc-selected-count", "0 of " + total);
    wireObjectRows();
    try {{
      sessionStorage.setItem(SC_CACHE_KEY, JSON.stringify({{
        sid: scSessionId(), payload: payload,
      }}));
    }} catch (err) {{}}
    if (typeof window.syncScFrameHeight === "function") window.syncScFrameHeight();
  }}

  function showObject(key) {{
    const obj = objectMap[key];
    if (!obj) return;
    selectedKey = key;
    document.querySelectorAll(".sc-object-row").forEach(function (row) {{
      row.classList.toggle("bg-secondary-container", row.dataset.objectKey === key);
    }});
    setText("sc-detail-type", obj.type_label || obj.object_type || "—");
    setText("sc-detail-schema", (obj.schema || "—").toUpperCase());
    setText("sc-detail-object", (obj.name || "—").toUpperCase());
    const src = document.getElementById("sc-diff-source");
    const tgt = document.getElementById("sc-diff-target");
    if (src) src.innerHTML = obj.diff_source_html || "<div class=\\"flex text-secondary\\"><span class=\\"diff-line-num\\">—</span>No source DDL</div>";
    if (tgt) tgt.innerHTML = obj.diff_target_html || "<div class=\\"flex text-secondary\\"><span class=\\"diff-line-num\\">—</span>No target DDL</div>";
    const summary = document.getElementById("sc-summary-content");
    if (summary) summary.innerHTML = obj.summary_html || "<p>No summary.</p>";
  }}

  function wireObjectRows() {{
    document.querySelectorAll(".sc-object-row").forEach(function (row) {{
      row.addEventListener("click", function () {{
        showObject(row.dataset.objectKey || "");
      }});
    }});
    if (selectedKey && objectMap[selectedKey]) showObject(selectedKey);
    else {{
      const first = document.querySelector(".sc-object-row");
      if (first) showObject(first.dataset.objectKey || "");
    }}
  }}

  function setActiveTab(tab) {{
    activeTab = tab;
    const sqlView = document.getElementById("tab-sql-view");
    const summaryView = document.getElementById("tab-summary");
    const syncView = document.getElementById("tab-sync");
    const tabs = ["sc-tab-sql", "sc-tab-summary", "sc-tab-sync"];
    tabs.forEach(function (id) {{
      const btn = document.getElementById(id);
      if (!btn) return;
      const active = (tab === "sql" && id === "sc-tab-sql") ||
        (tab === "summary" && id === "sc-tab-summary") ||
        (tab === "sync" && id === "sc-tab-sync");
      btn.className = active
        ? "px-md h-8 flex items-center text-body-sm font-bold text-primary border-b-2 border-primary transition-colors"
        : "px-md h-8 flex items-center text-body-sm font-medium text-secondary hover:bg-surface-container-high transition-colors";
    }});
    if (sqlView) sqlView.classList.toggle("hidden", tab !== "sql");
    if (summaryView) summaryView.classList.toggle("hidden", tab !== "summary");
    if (syncView) syncView.classList.toggle("hidden", tab !== "sync");
  }}

  async function runComparison() {{
    if (compareInFlight) return;
    const btn = document.getElementById("sc-refresh-btn");
    const originalHtml = btn ? btn.innerHTML : "";
    compareInFlight = true;
    if (btn) {{
      btn.disabled = true;
      btn.innerHTML = '<span class="material-symbols-outlined text-[18px] animate-spin">sync</span>Refreshing…';
    }}
    try {{
      const response = await fetch(apiUrl(RUN_COMPARE_URL), {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ sch_sid: scSessionId(), sch_token: scSessionToken() }}),
      }});
      const contentType = (response.headers.get("content-type") || "").toLowerCase();
      if (!contentType.includes("application/json")) {{
        toast("Comparison API unavailable — reloading with server run.", true);
        scNavigate(new URLSearchParams([["sch_action", "refresh"]]));
        return;
      }}
      let payload = {{ ok: false, error: "Comparison failed." }};
      try {{
        payload = await response.json();
      }} catch (parseErr) {{
        toast("Comparison API unavailable — reloading with server run.", true);
        scNavigate(new URLSearchParams([["sch_action", "refresh"]]));
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
      compareInFlight = false;
      if (btn) {{
        btn.disabled = false;
        btn.innerHTML = originalHtml ||
          '<span class="material-symbols-outlined text-[18px]">compare</span>Refresh';
      }}
    }}
  }}

  function restoreCachedComparisonIfNeeded() {{
    try {{
      const raw = sessionStorage.getItem(SC_CACHE_KEY);
      if (!raw) return;
      const cached = JSON.parse(raw);
      if (cached.sid && cached.sid !== scSessionId()) return;
      const tbody = document.getElementById("sc-results-tbody");
      const hasRows = tbody && tbody.querySelector(".sc-object-row");
      if (hasRows) return;
      if (cached.payload) applyComparisonResults(cached.payload);
    }} catch (err) {{}}
  }}

  document.getElementById("sc-home-back")?.addEventListener("click", function (e) {{
    e.preventDefault();
    navigateHomeClear();
  }});

  document.getElementById("sc-edit-creds")?.addEventListener("click", function (e) {{
    e.preventDefault();
    const editBtn = document.getElementById("sc-edit-creds");
    const sid = scSessionId();
    const token = scSessionToken();
    if (!sid || !token) {{ toast("Session expired — connect again.", true); return; }}
    if (editBtn) editBtn.disabled = true;
    fetch(apiUrl(CREATE_BIND_URL), {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ sch_sid: sid, sch_token: token }}),
    }}).then(function (res) {{
      return res.json().then(function (payload) {{
        return {{ res: res, payload: payload }};
      }});
    }}).then(function (out) {{
        if (!out.res.ok || !out.payload.ok || !out.payload.sch_bind) {{
          toast((out.payload && out.payload.error) || "Could not open edit.", true);
          return;
        }}
        const p = new URLSearchParams();
        p.set("sch_action", "edit");
        p.set("sch_bind", out.payload.sch_bind);
        scNavigate(p);
      }})
      .catch(function (err) {{
        toast(err.message || "Could not open edit.", true);
      }})
      .finally(function () {{
        if (editBtn) editBtn.disabled = false;
      }});
  }});

  document.getElementById("sc-refresh-btn")?.addEventListener("click", function (e) {{
    e.preventDefault(); runComparison();
  }});

  document.getElementById("sc-search")?.addEventListener("input", function (e) {{
    const q = (e.target.value || "").toLowerCase();
    document.querySelectorAll(".sc-object-row").forEach(function (row) {{
      const text = (row.textContent || "").toLowerCase();
      row.style.display = !q || text.indexOf(q) >= 0 ? "" : "none";
    }});
  }});

  document.getElementById("sc-tab-sql")?.addEventListener("click", function (e) {{
    e.preventDefault(); setActiveTab("sql");
  }});
  document.getElementById("sc-tab-summary")?.addEventListener("click", function (e) {{
    e.preventDefault(); setActiveTab("summary");
  }});
  document.getElementById("sc-tab-sync")?.addEventListener("click", function (e) {{
    e.preventDefault(); setActiveTab("sync");
  }});

  restoreCachedComparisonIfNeeded();
  wireObjectRows();
  setActiveTab("sql");

  {f'toast({_js_literal(view.toast_message)}, {json.dumps(view.toast_error)});' if view.toast_message else ''}
}})();
</script>
<div id="sc-toast" style="display:none"></div>
"""


def _wire_sc_setup_document(source: str, view: SchemaCompareSetupView) -> str:
    doc = source
    close_btn = (
        '<button aria-label="Close modal" id="sc-close-btn" type="button" '
        'class="w-10 h-10 flex items-center justify-center rounded-full '
        'hover:bg-surface-container-high transition-colors">'
        '<span class="material-symbols-outlined text-outline">close</span></button>'
    )
    back_btn = (
        '<button aria-label="Back to workspace" id="sc-close-btn" type="button" '
        'class="flex items-center gap-1 text-on-secondary-container hover:text-primary '
        'transition-colors text-sm font-medium">'
        '<span class="material-symbols-outlined text-sm">arrow_back</span>Back</button>'
    )
    doc = _regex_inject(
        _SC_CLOSE_BTN_MICRO,
        back_btn if view.edit_mode else close_btn,
        doc,
        count=1,
    )
    if view.edit_mode:
        doc = doc.replace(
            "<h1 class=\"font-headline-md text-headline-md text-on-surface\">New Comparison Project</h1>",
            "<h1 class=\"font-headline-md text-headline-md text-on-surface\">Edit Connection Settings</h1>",
            1,
        )

    doc = doc.replace(
        '<div id="sc-gitlab-repo-label" class="flex items-center gap-xs text-body-md"><!-- injected from db2_explorer/gitlab/client.py --></div>',
        f'<div id="sc-gitlab-repo-label" class="flex items-center gap-xs text-body-md">{_gitlab_repo_label_html()}</div>',
        1,
    )

    doc = doc.replace(
        'id="sc-gitlab-token" class="w-full h-10 px-md border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" placeholder="glpat-xxxxxxxxxxxx" type="password"',
        f'id="sc-gitlab-token" class="w-full h-10 px-md border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" placeholder="glpat-xxxxxxxxxxxx" type="password" value="{html.escape(view.gitlab_token)}"',
        1,
    )
    doc = doc.replace(
        'id="sc-az-server" class="w-full h-10 px-md border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" placeholder="az-db-prod-sql.database.windows.net" type="text"',
        f'id="sc-az-server" class="w-full h-10 px-md border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" placeholder="az-db-prod-sql.database.windows.net" type="text" value="{html.escape(view.az_server)}"',
        1,
    )
    if view.az_trust_cert:
        doc = doc.replace(
            '<input id="sc-az-trust-cert" type="checkbox" class="rounded',
            '<input id="sc-az-trust-cert" type="checkbox" checked class="rounded',
            1,
        )
    doc = doc.replace(
        '<input id="sc-auth-entra" type="radio" name="auth_type_modal" value="entra" class="w-4 h-4 text-primary border-outline focus:ring-primary" checked="">',
        f'<input id="sc-auth-entra" type="radio" name="auth_type_modal" value="entra" class="w-4 h-4 text-primary border-outline focus:ring-primary" {_auth_entra_checked(view.az_auth)}>',
        1,
    )
    doc = doc.replace(
        '<input id="sc-auth-windows" type="radio" name="auth_type_modal" value="windows" class="w-4 h-4 text-primary border-outline focus:ring-primary">',
        f'<input id="sc-auth-windows" type="radio" name="auth_type_modal" value="windows" class="w-4 h-4 text-primary border-outline focus:ring-primary" {_auth_windows_checked(view.az_auth)}>',
        1,
    )

    doc = doc.replace(
        'id="sc-branch" type="text" autocomplete="off" placeholder="Type to search branches…" class="w-full h-10 pl-md pr-10 border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" value=""',
        f'id="sc-branch" type="text" autocomplete="off" placeholder="Type to search branches…" class="w-full h-10 pl-md pr-10 border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" value="{html.escape(view.branch)}"',
        1,
    )
    doc = doc.replace(
        'id="sc-database" type="text" autocomplete="off" placeholder="Type to search database folders…" class="w-full h-10 pl-md pr-10 border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" value=""',
        f'id="sc-database" type="text" autocomplete="off" placeholder="Type to search database folders…" class="w-full h-10 pl-md pr-10 border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" value="{html.escape(view.database)}"',
        1,
    )
    doc = doc.replace(
        'id="sc-server" type="text" autocomplete="off" placeholder="Type to search server folders…" class="w-full h-10 pl-md pr-10 border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" value=""',
        f'id="sc-server" type="text" autocomplete="off" placeholder="Type to search server folders…" class="w-full h-10 pl-md pr-10 border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" value="{html.escape(view.server)}"',
        1,
    )
    doc = doc.replace(
        'id="sc-az-database" type="text" autocomplete="off" placeholder="Type to search databases…" class="w-full h-10 pl-md pr-10 border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" value=""',
        f'id="sc-az-database" type="text" autocomplete="off" placeholder="Type to search databases…" class="w-full h-10 pl-md pr-10 border border-outline focus:border-primary focus:ring-1 focus:ring-primary rounded bg-white text-body-md" value="{html.escape(view.az_database)}"',
        1,
    )

    doc = _regex_inject(_SC_SETUP_MICRO, _sc_setup_bridge_script(view), doc, count=1)
    doc = doc.replace("</body>", _FULL_HEIGHT_SCRIPT + "</body>")
    return doc


def _wire_sc_workspace_document(source: str, view: SchemaCompareWorkspaceView) -> str:
    doc = source
    summary = view.summary or {}
    total = summary.get("total", 0)
    doc = doc.replace(">0 of 0<", f">{total}<", 1) if "0 of 0" in doc else doc
    doc = doc.replace(
        '<div id="sc-selected-count" class="text-body-md font-bold text-on-surface">0 of 0</div>',
        f'<div id="sc-selected-count" class="text-body-md font-bold text-on-surface">0 of {total}</div>',
        1,
    )
    doc = doc.replace(
        '<span id="sc-source-label" class="text-body-md font-bold text-on-surface">GitLab Source</span>',
        f'<span id="sc-source-label" class="text-body-md font-bold text-on-surface">{html.escape(view.source_label)}</span>',
        1,
    )
    doc = doc.replace(
        '<span id="sc-target-label" class="text-body-md font-bold text-on-surface">Azure SQL Target</span>',
        f'<span id="sc-target-label" class="text-body-md font-bold text-on-surface">{html.escape(view.target_label)}</span>',
        1,
    )
    tbody_html = view.table_html or (
        '<tr><td colspan="7" class="px-md py-lg text-center text-secondary">'
        "Run comparison to see results.</td></tr>"
    )
    doc = _regex_inject(
        _SC_TBODY_MICRO,
        f'<tbody id="sc-results-tbody" class="text-body-sm">{tbody_html}</tbody>',
        doc,
        count=1,
    )
    doc = _regex_inject(_SC_WORKSPACE_MICRO, _sc_workspace_bridge_script(view), doc, count=1)
    doc = doc.replace("</body>", _WORKSPACE_FRAME_HEIGHT_SCRIPT + "</body>")
    return doc


def render_schema_compare_setup_page(view: SchemaCompareSetupView) -> None:
    inject_shell_component(tailwind_config_source="schema_setup")
    from db2_explorer.ui import stitch_shell as _shell

    _shell._HTML_CACHE.pop("schema_setup", None)
    doc = _wire_sc_setup_document(_read_html("schema_setup"), view)
    st.markdown(f"<style>{shell_iframe_css()}</style>", unsafe_allow_html=True)
    components.html(doc, height=900, scrolling=False)


def render_schema_compare_workspace_page(view: SchemaCompareWorkspaceView) -> None:
    inject_shell_component(tailwind_config_source="schema_workspace")
    from db2_explorer.ui import stitch_shell as _shell

    _shell._HTML_CACHE.pop("schema_workspace", None)
    doc = _wire_sc_workspace_document(_read_html("schema_workspace"), view)
    st.markdown(
        f"<style>{shell_iframe_css()}{_SC_WORKSPACE_SHELL_CSS}</style>",
        unsafe_allow_html=True,
    )
    components.html(doc, height=900, scrolling=False)
