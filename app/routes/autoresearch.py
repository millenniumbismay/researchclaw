"""AutoResearch routes — project management and context pipeline."""

import logging

from fastapi import APIRouter, HTTPException

from app.models.autoresearch import (
    AddGithubRepoRequest,
    AddPapersRequest,
    CreateProjectRequest,
    FetchPaperRequest,
    ProjectStatusResponse,
)
from app.services import autoresearch_project_service as project_svc
from app.services import autoresearch_context_service as context_svc

logger = logging.getLogger(__name__)

router = APIRouter(tags=["autoresearch"])


# ============================================================
# Project CRUD
# ============================================================

@router.get("/api/autoresearch/projects")
async def list_projects():
    return project_svc.list_projects()


@router.post("/api/autoresearch/projects")
async def create_project(body: CreateProjectRequest):
    state = project_svc.create_project(body.name, body.description)
    return state.model_dump()


@router.get("/api/autoresearch/projects/{project_id}")
async def get_project(project_id: str):
    state = project_svc.get_project(project_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    build_status = context_svc.get_build_status(project_id)
    progress = context_svc.get_build_progress(project_id)
    return {
        **state.model_dump(),
        "build_status": build_status,
        "build_progress": progress,
    }


@router.delete("/api/autoresearch/projects/{project_id}")
async def delete_project(project_id: str):
    project_svc.delete_project(project_id)
    return {"status": "deleted"}


# ============================================================
# Paper management
# ============================================================

@router.post("/api/autoresearch/projects/{project_id}/papers")
async def add_papers(project_id: str, body: AddPapersRequest):
    state = project_svc.add_papers(project_id, body.paper_ids)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return state.model_dump()


@router.delete("/api/autoresearch/projects/{project_id}/papers/{paper_id:path}")
async def remove_paper(project_id: str, paper_id: str):
    state = project_svc.remove_paper(project_id, paper_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return state.model_dump()


@router.post("/api/autoresearch/projects/{project_id}/fetch-paper")
async def fetch_paper(project_id: str, body: FetchPaperRequest):
    paper = context_svc.fetch_paper_by_url(body.arxiv_url)
    if paper is None:
        raise HTTPException(status_code=400, detail="Could not fetch paper. Check the arXiv URL.")
    # Also add to project
    state = project_svc.add_papers(project_id, [paper["id"]])
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"paper": paper, "state": state.model_dump()}


# ============================================================
# GitHub repos
# ============================================================

@router.post("/api/autoresearch/projects/{project_id}/github")
async def add_github_repo(project_id: str, body: AddGithubRepoRequest):
    state = project_svc.add_github_repo(project_id, body.url)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return state.model_dump()


@router.delete("/api/autoresearch/projects/{project_id}/github")
async def remove_github_repo(project_id: str, body: AddGithubRepoRequest):
    state = project_svc.remove_github_repo(project_id, body.url)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return state.model_dump()


# ============================================================
# Context building
# ============================================================

@router.post("/api/autoresearch/projects/{project_id}/build-context")
async def build_context(project_id: str):
    state = project_svc.get_project(project_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not state.project.paper_ids:
        raise HTTPException(status_code=400, detail="Add at least one paper before building context")
    context_svc.build_context(project_id)
    return {"status": "building", "project_id": project_id}


@router.get("/api/autoresearch/projects/{project_id}/context")
async def get_context(project_id: str):
    state = project_svc.get_project(project_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    build_status = context_svc.get_build_status(project_id)
    progress = context_svc.get_build_progress(project_id)
    return {
        "build_status": build_status,
        "build_progress": progress,
        "paper_contexts": [pc.model_dump() for pc in state.paper_contexts],
        "phase": state.project.phase,
    }
