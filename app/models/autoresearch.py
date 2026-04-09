"""Pydantic models for AutoResearch — paper-to-code multi-agent feature."""

import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# Paper context
# ============================================================

class RepoAnalysis(BaseModel):
    repo_url: str
    structure: str = ""
    key_files: list[str] = Field(default_factory=list)
    architecture_notes: str = ""
    dependencies: list[str] = Field(default_factory=list)
    language_breakdown: dict[str, float] = Field(default_factory=dict)


class PaperContext(BaseModel):
    paper_id: str
    title: str
    content_summary: str = ""
    key_methods: list[str] = Field(default_factory=list)
    key_algorithms: list[str] = Field(default_factory=list)
    github_repo_url: Optional[str] = None
    repo_analysis: Optional[RepoAnalysis] = None


# ============================================================
# Agent interaction (Phase B)
# ============================================================

class AgentMessage(BaseModel):
    role: str  # user | planner | developer | reviewer_critic | reviewer_tester | reviewer_advocate | system
    content: str
    agent_name: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    metadata: dict = Field(default_factory=dict)


class PlanModule(BaseModel):
    name: str
    description: str
    files: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    estimated_complexity: str = "medium"  # low | medium | high


class ImplementationPlan(BaseModel):
    modules: list[PlanModule] = Field(default_factory=list)
    architecture_notes: str = ""
    dependencies: list[str] = Field(default_factory=list)
    approved: bool = False
    approved_at: Optional[str] = None


# ============================================================
# Code artifacts (Phase B/C)
# ============================================================

class CodeArtifact(BaseModel):
    file_path: str
    content: str
    language: str = "python"
    iteration: int
    created_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


class ReviewFinding(BaseModel):
    reviewer_role: str  # critic | tester | advocate
    severity: str  # blocker | major | minor | suggestion
    file_path: str
    line_range: str = ""
    description: str
    suggestion: str = ""


class ReviewRound(BaseModel):
    iteration: int
    findings: list[ReviewFinding] = Field(default_factory=list)
    verdict: str  # approve | revise | major_revise
    summary: str
    created_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


class DevIteration(BaseModel):
    iteration: int
    code_artifacts: list[CodeArtifact] = Field(default_factory=list)
    review: Optional[ReviewRound] = None
    developer_notes: str = ""
    created_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


# ============================================================
# Project
# ============================================================

class AutoResearchProject(BaseModel):
    project_id: str
    name: str
    description: str = ""
    paper_ids: list[str] = Field(default_factory=list)
    github_repos: list[str] = Field(default_factory=list)
    status: str = "setup"  # setup | planning | developing | reviewing | awaiting_user | complete | error
    phase: str = "paper_selection"  # paper_selection | context_gathering | planning_chat | plan_finalized | dev_cycle | complete
    current_iteration: int = 0
    max_iterations: int = 5
    repo_path: Optional[str] = None  # Absolute path to the project git repo
    claude_code_session_id: Optional[str] = None  # For resuming Claude Code sessions
    created_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


# ============================================================
# Full state (persisted per project)
# ============================================================

class AutoResearchState(BaseModel):
    project: AutoResearchProject
    paper_contexts: list[PaperContext] = Field(default_factory=list)
    plan: Optional[ImplementationPlan] = None
    planning_chat: list[AgentMessage] = Field(default_factory=list)
    iterations: list[DevIteration] = Field(default_factory=list)
    orchestrator_log: list[AgentMessage] = Field(default_factory=list)


# ============================================================
# Request / Response models
# ============================================================

class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


class AddPapersRequest(BaseModel):
    paper_ids: list[str]


class AddGithubRepoRequest(BaseModel):
    url: str


class FetchPaperRequest(BaseModel):
    arxiv_url: str


class ProjectStatusResponse(BaseModel):
    project_id: str
    status: str
    phase: str
    current_iteration: int
    needs_input: bool = False
    needs_input_type: Optional[str] = None
    state: AutoResearchState


class UserDecisionRequest(BaseModel):
    decision: str  # approve | revise | guide
    guidance: str = ""  # User instructions for next iteration (when decision=guide)


class AgentStreamEvent(BaseModel):
    event_type: str  # message | tool_use | tool_result | complete | error
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    metadata: dict = Field(default_factory=dict)
