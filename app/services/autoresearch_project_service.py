"""AutoResearch Project Service — CRUD and state persistence."""

import datetime
import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.autoresearch import (
    AutoResearchProject,
    AutoResearchState,
)
from app.utils import load_json, save_json

logger = logging.getLogger(__name__)

# Per-project locks for concurrent access
_project_locks: dict[str, threading.Lock] = {}
_project_locks_lock = threading.Lock()

# Lock for projects.json index file (cross-project)
_index_lock = threading.Lock()


def _get_project_lock(project_id: str) -> threading.Lock:
    with _project_locks_lock:
        if project_id not in _project_locks:
            _project_locks[project_id] = threading.Lock()
        return _project_locks[project_id]


# ============================================================
# Paths
# ============================================================

def _projects_index_path() -> Path:
    return settings.autoresearch_dir / "projects.json"


def _project_dir(project_id: str) -> Path:
    return settings.autoresearch_dir / project_id


def _state_path(project_id: str) -> Path:
    return _project_dir(project_id) / "state.json"


# ============================================================
# Index management
# ============================================================

def _load_index() -> list[dict]:
    return load_json(_projects_index_path(), [])


def _save_index(index: list[dict]) -> None:
    save_json(_projects_index_path(), index)


def _update_index_entry(project: AutoResearchProject) -> None:
    with _index_lock:
        index = _load_index()
        entry = {
            "project_id": project.project_id,
            "name": project.name,
            "status": project.status,
            "phase": project.phase,
            "paper_count": len(project.paper_ids),
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }
        for i, e in enumerate(index):
            if e["project_id"] == project.project_id:
                index[i] = entry
                _save_index(index)
                return
        index.append(entry)
        _save_index(index)


def _remove_index_entry(project_id: str) -> None:
    with _index_lock:
        index = _load_index()
        index = [e for e in index if e["project_id"] != project_id]
        _save_index(index)


# ============================================================
# CRUD
# ============================================================

def list_projects() -> list[dict]:
    return _load_index()


def create_project(name: str, description: str = "") -> AutoResearchState:
    project_id = uuid.uuid4().hex[:12]
    now = datetime.datetime.utcnow().isoformat()
    project = AutoResearchProject(
        project_id=project_id,
        name=name,
        description=description,
        created_at=now,
        updated_at=now,
    )
    state = AutoResearchState(project=project)
    _project_dir(project_id).mkdir(parents=True, exist_ok=True)
    save_state(state)
    return state


def get_project(project_id: str) -> Optional[AutoResearchState]:
    path = _state_path(project_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AutoResearchState(**data)
    except Exception as e:
        logger.error(f"Failed to load project {project_id}: {e}")
        return None


def save_state(state: AutoResearchState) -> None:
    state.project.updated_at = datetime.datetime.utcnow().isoformat()
    folder = _project_dir(state.project.project_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "state.json").write_text(
        state.model_dump_json(indent=2), encoding="utf-8"
    )
    _update_index_entry(state.project)


def delete_project(project_id: str) -> bool:
    import shutil
    # Clean up the git repo directory if it exists
    state = get_project(project_id)
    if state and state.project.repo_path:
        from pathlib import Path
        repo_dir = Path(state.project.repo_path)
        if repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)
    # Clean up state directory
    folder = _project_dir(project_id)
    if folder.exists():
        shutil.rmtree(folder)
    _remove_index_entry(project_id)
    with _project_locks_lock:
        _project_locks.pop(project_id, None)
    return True


# ============================================================
# Paper / Repo management
# ============================================================

def add_papers(project_id: str, paper_ids: list[str]) -> Optional[AutoResearchState]:
    with _get_project_lock(project_id):
        state = get_project(project_id)
        if state is None:
            return None
        for pid in paper_ids:
            if pid not in state.project.paper_ids:
                state.project.paper_ids.append(pid)
        save_state(state)
        return state


def remove_paper(project_id: str, paper_id: str) -> Optional[AutoResearchState]:
    with _get_project_lock(project_id):
        state = get_project(project_id)
        if state is None:
            return None
        state.project.paper_ids = [p for p in state.project.paper_ids if p != paper_id]
        state.paper_contexts = [pc for pc in state.paper_contexts if pc.paper_id != paper_id]
        save_state(state)
        return state


def add_github_repo(project_id: str, url: str) -> Optional[AutoResearchState]:
    with _get_project_lock(project_id):
        state = get_project(project_id)
        if state is None:
            return None
        if url not in state.project.github_repos:
            state.project.github_repos.append(url)
        save_state(state)
        return state


def remove_github_repo(project_id: str, url: str) -> Optional[AutoResearchState]:
    with _get_project_lock(project_id):
        state = get_project(project_id)
        if state is None:
            return None
        state.project.github_repos = [r for r in state.project.github_repos if r != url]
        save_state(state)
        return state
