"""AutoResearch routes — project management, context pipeline, and agent loop."""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.autoresearch import (
    AddGithubRepoRequest,
    AddPapersRequest,
    CreateProjectRequest,
    FetchPaperRequest,
    ProjectStatusResponse,
    UserDecisionRequest,
)
from app.services import autoresearch_project_service as project_svc
from app.services import autoresearch_context_service as context_svc
from app.services import autoresearch_orchestrator as orchestrator

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
    if orchestrator.is_agent_running(project_id):
        raise HTTPException(status_code=409, detail="Cannot delete while an agent is running")
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


# ============================================================
# Planning
# ============================================================

@router.post("/api/autoresearch/projects/{project_id}/start-planning")
async def start_planning_route(project_id: str):
    state = project_svc.get_project(project_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not state.paper_contexts:
        raise HTTPException(status_code=400, detail="Build context before planning")
    result = await orchestrator.start_planning(project_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/api/autoresearch/projects/{project_id}/plan/chat")
async def plan_chat(project_id: str, body: dict):
    message = body.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    state = project_svc.get_project(project_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    result = await orchestrator.handle_plan_chat(project_id, message)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/api/autoresearch/projects/{project_id}/plan/approve")
async def approve_plan_route(project_id: str):
    state = project_svc.get_project(project_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    result = orchestrator.approve_plan(project_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ============================================================
# Development cycle
# ============================================================

@router.post("/api/autoresearch/projects/{project_id}/start-dev")
async def start_dev(project_id: str):
    state = project_svc.get_project(project_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    result = orchestrator.start_dev_cycle(project_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/api/autoresearch/projects/{project_id}/start-review")
async def start_review_route(project_id: str):
    state = project_svc.get_project(project_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")
    result = orchestrator.start_review(project_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/api/autoresearch/projects/{project_id}/iteration/{iteration_num}")
async def get_iteration(project_id: str, iteration_num: int):
    result = orchestrator.get_iteration_details(project_id, iteration_num)
    if result is None:
        raise HTTPException(status_code=404, detail="Iteration not found")
    return result


@router.post("/api/autoresearch/projects/{project_id}/decision")
async def user_decision(project_id: str, body: UserDecisionRequest):
    if body.decision not in ("approve", "revise", "guide"):
        raise HTTPException(status_code=400, detail="Decision must be approve, revise, or guide")
    result = orchestrator.handle_user_decision(project_id, body.decision, body.guidance)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/api/autoresearch/projects/{project_id}/diff/{from_iter}/{to_iter}")
async def get_diff(project_id: str, from_iter: int, to_iter: int):
    diff = orchestrator.get_project_diff(project_id, from_iter, to_iter)
    if diff is None:
        raise HTTPException(status_code=404, detail="Diff not available")
    return {"diff": diff}


# ============================================================
# SSE streaming for agent activity
# ============================================================

@router.get("/api/autoresearch/projects/{project_id}/stream")
async def stream_events(project_id: str):
    """SSE endpoint for real-time agent activity."""
    state = project_svc.get_project(project_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Project not found")

    async def event_generator():
        import time
        index = 0
        start_time = time.monotonic()
        max_duration = 30 * 60  # 30 minutes

        while True:
            # Timeout guard
            if time.monotonic() - start_time > max_duration:
                yield f"data: {json.dumps({'event_type': 'error', 'content': 'Stream timeout (30 min)'})}\n\n"
                yield f"data: {json.dumps({'event_type': 'stream_end'})}\n\n"
                return

            events = orchestrator.get_events(project_id, after_index=index)
            for event in events:
                data = json.dumps(event.model_dump())
                yield f"data: {data}\n\n"
                index += 1

                # Stop streaming after completion or error
                if event.event_type in ("complete", "error"):
                    yield f"data: {json.dumps({'event_type': 'stream_end'})}\n\n"
                    return

            await asyncio.sleep(0.5)

            # Safety: if no agent running and no new events, end stream
            if not orchestrator.is_agent_running(project_id) and not events:
                yield f"data: {json.dumps({'event_type': 'stream_end'})}\n\n"
                return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
