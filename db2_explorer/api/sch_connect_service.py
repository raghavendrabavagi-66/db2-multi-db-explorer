"""Schema Compare connection helpers for the background API server."""

from __future__ import annotations

from typing import Any

from db2_explorer.api.sch_credential_store import (
    create_bind_token,
    get_connect_payload,
    has_connect_session,
    save_connect_payload,
    verify_connect_token,
)
from db2_explorer.api.sch_result_store import invalidate_if_credentials_changed
from db2_explorer.clients.azure import AUTH_METHOD_LABELS, AzureConnection, query as azure_query, test_connection as test_azure
from db2_explorer.gitlab.client import GITLAB_BASE_URL, GITLAB_PROJECT_ID, GitLabClient, make_gitlab_config
from db2_explorer.gitlab.deployment_parser import OBJECT_TYPE_FILES

_AZ_AUTH_MAP = {
    "entra": "azure_ad_interactive",
    "azure_ad_interactive": "azure_ad_interactive",
    "windows": "windows_integrated",
    "windows_integrated": "windows_integrated",
}


def _azure_auth_method(raw: str) -> str:
    return _AZ_AUTH_MAP.get(str(raw or "entra").lower(), "azure_ad_interactive")


def _gitlab_client(token: str, branch: str = "main") -> GitLabClient | None:
    cfg = make_gitlab_config(token, branch)
    if not cfg:
        return None
    return GitLabClient(cfg)


def list_branches_json(body: dict[str, Any]) -> dict[str, Any]:
    token = str(body.get("gitlab_token", "")).strip()
    if not token:
        return {"ok": False, "error": "GitLab personal access token is required."}
    client = _gitlab_client(token)
    if client is None:
        return {"ok": False, "error": "Invalid GitLab token."}
    out = client.list_branches()
    if not out.ok:
        return {"ok": False, "error": out.error or "Failed to list branches."}
    branches = list(out.data or [])
    return {"ok": True, "branches": branches, "message": f"Found {len(branches)} branch(es)."}


def list_db_folders_json(body: dict[str, Any]) -> dict[str, Any]:
    token = str(body.get("gitlab_token", "")).strip()
    branch = str(body.get("branch", "main")).strip() or "main"
    if not token:
        return {"ok": False, "error": "GitLab personal access token is required."}
    client = _gitlab_client(token, branch)
    if client is None:
        return {"ok": False, "error": "Invalid GitLab token."}
    out = client.list_db_folders(branch)
    if not out.ok:
        return {"ok": False, "error": out.error or "Failed to list database folders."}
    folders = list(out.data or [])
    return {"ok": True, "folders": folders}


def list_server_folders_json(body: dict[str, Any]) -> dict[str, Any]:
    token = str(body.get("gitlab_token", "")).strip()
    branch = str(body.get("branch", "main")).strip() or "main"
    database = str(body.get("database", "")).strip()
    if not token:
        return {"ok": False, "error": "GitLab personal access token is required."}
    if not database:
        return {"ok": False, "error": "Database folder is required."}
    client = _gitlab_client(token, branch)
    if client is None:
        return {"ok": False, "error": "Invalid GitLab token."}
    out = client.list_server_folders(database, branch)
    if not out.ok:
        return {"ok": False, "error": out.error or "Failed to list server folders."}
    folders = list(out.data or [])
    return {"ok": True, "folders": folders}


def load_deployment_json(body: dict[str, Any]) -> dict[str, Any]:
    token = str(body.get("gitlab_token", "")).strip()
    branch = str(body.get("branch", "main")).strip() or "main"
    database = str(body.get("database", "")).strip()
    server_folder = str(body.get("server_folder", "")).strip()
    if not token:
        return {"ok": False, "error": "GitLab personal access token is required."}
    if not database or not server_folder:
        return {"ok": False, "error": "Database and server folder are required."}
    client = _gitlab_client(token, branch)
    if client is None:
        return {"ok": False, "error": "Invalid GitLab token."}
    filenames = list(OBJECT_TYPE_FILES.values())
    out = client.fetch_deployment_files(database, server_folder, branch, filenames)
    if not out.ok:
        return {"ok": False, "error": out.error or "Failed to load deployment."}
    payload = out.data or {}
    files = dict(payload.get("files") or {})
    missing = list(payload.get("missing") or [])
    bundle_path = str(payload.get("bundle_path") or "")

    mig_az_server = ""
    mig_az_database = ""
    mig_branch = branch
    info = client.fetch_migration_info(database, server_folder, branch)
    if info.ok and info.data:
        mig = info.data
        mig_az_server = str(mig.get("target_server", "") or "").strip()
        mig_az_database = str(mig.get("target_database", "") or "").strip()
        mig_branch = str(mig.get("branch", "") or branch).strip() or branch

    return {
        "ok": True,
        "message": f"Loaded {len(files)} file(s) from `{bundle_path}`.",
        "deployment_files": files,
        "missing_files": missing,
        "bundle_path": bundle_path,
        "target_server": mig_az_server,
        "target_database": mig_az_database,
        "migration_branch": mig_branch,
        "gitlab_base_url": GITLAB_BASE_URL,
        "gitlab_project_id": GITLAB_PROJECT_ID,
    }


def test_azure_json(body: dict[str, Any]) -> dict[str, Any]:
    server = str(body.get("server", "")).strip()
    database = str(body.get("database", "")).strip()
    auth_raw = str(body.get("auth_method", "entra")).strip().lower()
    auth_method = _azure_auth_method(auth_raw)
    trust = bool(body.get("trust_server_certificate", False))

    if not all([server, database]):
        return {"ok": False, "error": "Server and Database are required."}

    az_conn = AzureConnection(
        server=server,
        database=database,
        auth_method=auth_method,
        trust_server_certificate=trust,
    )
    out = test_azure(az_conn)
    if out.ok:
        label = AUTH_METHOD_LABELS.get(auth_method, auth_method)
        return {"ok": True, "message": f"Target connection OK ({label})."}
    return {"ok": False, "error": out.error or "Target connection failed."}


def list_azure_databases_json(body: dict[str, Any]) -> dict[str, Any]:
    server = str(body.get("server", "")).strip()
    auth_raw = str(body.get("auth_method", "entra")).strip().lower()
    auth_method = _azure_auth_method(auth_raw)
    trust = bool(body.get("trust_server_certificate", False))

    if not server:
        return {"ok": False, "error": "Server is required."}

    az_conn = AzureConnection(
        server=server,
        database="master",
        auth_method=auth_method,
        trust_server_certificate=trust,
    )
    list_out = azure_query(
        az_conn,
        "SELECT name FROM sys.databases WHERE state_desc = 'ONLINE' ORDER BY name",
        (),
    )
    if not list_out.ok:
        return {"ok": False, "error": list_out.error or "Failed to list databases."}

    databases = [str(row.get("NAME", "")).strip() for row in list_out.rows]
    databases = [name for name in databases if name]
    if not databases:
        return {"ok": False, "error": "No online databases found on this server."}

    return {"ok": True, "databases": databases, "message": f"Found {len(databases)} database(s)."}


def save_connect_json(body: dict[str, Any]) -> dict[str, Any]:
    """Persist Schema Compare credentials server-side."""
    sch_sid = str(body.get("sch_sid", "")).strip()
    if not sch_sid:
        return {"ok": False, "error": "Session id is required."}

    gitlab_token = str(body.get("gitlab_token", "")).strip()
    branch = str(body.get("branch", "main")).strip() or "main"
    database = str(body.get("database", "")).strip()
    server_folder = str(body.get("server_folder", "")).strip()
    az_server = str(body.get("server", "")).strip()
    az_database = str(body.get("az_database", "")).strip()
    auth_raw = str(body.get("auth_method", "entra")).strip().lower()
    trust = bool(body.get("trust_server_certificate", False))
    deployment_files = body.get("deployment_files") or {}
    missing_files = body.get("missing_files") or []
    bundle_path = str(body.get("bundle_path", "")).strip()
    branch_list = body.get("branch_list") or []
    db_folder_list = body.get("db_folder_list") or []
    server_folder_list = body.get("server_folder_list") or []
    az_database_options = body.get("az_database_options") or []

    missing: list[str] = []
    if not gitlab_token:
        missing.append("GitLab token")
    if not database or not server_folder:
        missing.append("GitLab database and server folder")
    if not deployment_files:
        missing.append("deployment files (load deployment first)")
    if not all([az_server, az_database]):
        missing.append("Azure server and database")
    if missing:
        return {"ok": False, "error": "Missing: " + ", ".join(missing)}

    payload_data = {
        "sch_gitlab_token": gitlab_token,
        "sch_branch": branch,
        "sch_branch_list": list(branch_list),
        "sch_database": database,
        "sch_db_folder_list": list(db_folder_list),
        "sch_server": server_folder,
        "sch_server_folder_list": list(server_folder_list),
        "sch_az_server": az_server,
        "sch_az_database": az_database,
        "sch_az_database_options": list(az_database_options),
        "sch_az_auth": auth_raw,
        "sch_az_trust_cert": trust,
        "sch_deployment_files": dict(deployment_files),
        "sch_missing_files": list(missing_files),
        "sch_bundle_path": bundle_path,
    }

    sch_token_in = str(body.get("sch_token", "")).strip()
    old_payload: dict[str, Any] | None = None
    if has_connect_session(sch_sid):
        if not verify_connect_token(sch_sid, sch_token_in):
            return {"ok": False, "error": "Invalid session token."}
        old_payload = get_connect_payload(sch_sid, sch_token_in)

    invalidate_if_credentials_changed(sch_sid, old_payload, payload_data)

    sch_token = save_connect_payload(sch_sid, payload_data)
    sch_bind = create_bind_token(sch_sid, sch_token)
    return {
        "ok": True,
        "message": "Credentials saved.",
        "sch_token": sch_token,
        "sch_bind": sch_bind,
    }


def create_bind_json(body: dict[str, Any]) -> dict[str, Any]:
    sch_sid = str(body.get("sch_sid", "")).strip()
    sch_token = str(body.get("sch_token", "")).strip()
    if not sch_sid or not sch_token:
        return {"ok": False, "error": "Session id and token are required."}
    if not verify_connect_token(sch_sid, sch_token):
        return {"ok": False, "error": "Invalid or expired session. Connect again."}
    sch_bind = create_bind_token(sch_sid, sch_token)
    return {"ok": True, "sch_bind": sch_bind}
