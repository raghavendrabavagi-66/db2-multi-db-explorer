"""GitLab API client for deployment DDL files."""

from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass

import requests

ROOT_PATH = "db2automation_logs"


@dataclass
class GitLabConfig:
    base_url: str
    project_id: str
    token: str
    default_branch: str = "main"


@dataclass
class GitLabOutcome:
    data: object = None
    status: str = "ok"
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def load_gitlab_config() -> GitLabConfig | None:
    """Load GitLab settings from Streamlit secrets or environment variables."""
    base_url = ""
    project_id = ""
    token = ""
    default_branch = "main"

    try:
        import streamlit as st

        sec = st.secrets.get("gitlab", {})
        base_url = str(sec.get("base_url", "") or "")
        project_id = str(sec.get("project_id", "") or "")
        token = str(sec.get("token", "") or "")
        default_branch = str(sec.get("default_branch", "main") or "main")
    except Exception:
        pass

    base_url = base_url or os.environ.get("GITLAB_BASE_URL", "https://gitlab.com")
    project_id = project_id or os.environ.get("GITLAB_PROJECT_ID", "")
    token = token or os.environ.get("GITLAB_TOKEN", "")
    default_branch = os.environ.get("GITLAB_DEFAULT_BRANCH", default_branch)

    if not project_id or not token:
        return None
    return GitLabConfig(
        base_url=base_url.rstrip("/"),
        project_id=project_id,
        token=token,
        default_branch=default_branch,
    )


class GitLabClient:
    def __init__(self, config: GitLabConfig):
        self.config = config
        self._session = requests.Session()
        self._session.headers.update({"PRIVATE-TOKEN": config.token})

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}/api/v4/projects/{self.config.project_id}{path}"

    def list_tree(self, path: str, branch: str) -> GitLabOutcome:
        encoded = urllib.parse.quote(path, safe="")
        try:
            resp = self._session.get(
                self._url(f"/repository/tree?path={encoded}&ref={urllib.parse.quote(branch, safe='')}&per_page=100"),
                timeout=60,
            )
            if resp.status_code != 200:
                return GitLabOutcome(status="error", error=f"GitLab tree error ({resp.status_code}): {resp.text[:300]}")
            items = resp.json()
            names = sorted(
                item["name"]
                for item in items
                if item.get("type") == "tree" and item.get("name")
            )
            return GitLabOutcome(data=names)
        except requests.RequestException as exc:
            return GitLabOutcome(status="error", error=str(exc))

    def fetch_file_raw(self, relative_path: str, branch: str) -> GitLabOutcome:
        encoded = urllib.parse.quote(relative_path, safe="")
        try:
            resp = self._session.get(
                self._url(
                    f"/repository/files/{encoded}/raw?ref={urllib.parse.quote(branch, safe='')}"
                ),
                timeout=120,
            )
            if resp.status_code != 200:
                return GitLabOutcome(
                    status="error",
                    error=f"GitLab file error ({resp.status_code}): {resp.text[:300]}",
                )
            return GitLabOutcome(data=resp.text)
        except requests.RequestException as exc:
            return GitLabOutcome(status="error", error=str(exc))

    def list_db_folders(self, branch: str) -> GitLabOutcome:
        return self.list_tree(ROOT_PATH, branch)

    def list_server_folders(self, database: str, branch: str) -> GitLabOutcome:
        return self.list_tree(f"{ROOT_PATH}/{database}", branch)

    def resolve_deployment_bundle_path(
        self, database: str, server_folder: str, branch: str
    ) -> GitLabOutcome:
        """Return repo-relative path to step4_deployment bundle folder."""
        step_path = f"{ROOT_PATH}/{database}/{server_folder}/step4_deployment"
        out = self.list_tree(step_path, branch)
        if not out.ok:
            return out
        subfolders = out.data or []
        if not subfolders:
            return GitLabOutcome(status="error", error=f"No bundle folder under {step_path}")

        info = self.fetch_migration_info(database, server_folder, branch)
        if info.ok and info.data:
            server_name = str(info.data.get("server", "") or "").strip()
            if server_name and server_name in subfolders:
                return GitLabOutcome(data=f"{step_path}/{server_name}")
            hyphen = server_name.replace("_", "-") if server_name else ""
            if hyphen and hyphen in subfolders:
                return GitLabOutcome(data=f"{step_path}/{hyphen}")

        return GitLabOutcome(data=f"{step_path}/{subfolders[0]}")

    def fetch_migration_info(
        self, database: str, server_folder: str, branch: str
    ) -> GitLabOutcome:
        path = f"{ROOT_PATH}/{database}/{server_folder}/migration_info.txt"
        raw = self.fetch_file_raw(path, branch)
        if not raw.ok:
            return raw
        text = str(raw.data or "")
        info: dict[str, str] = {}
        for line in text.splitlines():
            m = re.match(r"^([^:]+):\s*(.+)$", line.strip())
            if not m:
                continue
            key = m.group(1).strip().lower().replace(" ", "_")
            info[key] = m.group(2).strip()
        mapping = {
            "database": info.get("database", database),
            "server": info.get("server", ""),
            "branch": info.get("branch", ""),
            "target_database": info.get("target_database", ""),
            "target_server": info.get("target_server", ""),
        }
        return GitLabOutcome(data=mapping)

    def fetch_deployment_files(
        self,
        database: str,
        server_folder: str,
        branch: str,
        filenames: list[str],
    ) -> GitLabOutcome:
        bundle = self.resolve_deployment_bundle_path(database, server_folder, branch)
        if not bundle.ok:
            return bundle
        bundle_path = str(bundle.data)
        files: dict[str, str] = {}
        missing_list: list[str] = []
        for name in filenames:
            rel = f"{bundle_path}/{name}"
            out = self.fetch_file_raw(rel, branch)
            if out.ok:
                files[name] = str(out.data or "")
            else:
                missing_list.append(name)
        return GitLabOutcome(data={"files": files, "missing": missing_list, "bundle_path": bundle_path})
