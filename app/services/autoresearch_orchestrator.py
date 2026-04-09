"""AutoResearch Orchestrator — state machine for the multi-agent dev loop.

Coordinates planning (via PlannerAgent), development (via Claude Code developer),
and review (via Claude Code reviewer) phases.  Exposes an event buffer for SSE
streaming to the frontend.
"""

import asyncio
import datetime
import logging
import re
import subprocess
import threading
from pathlib import Path
from typing import Optional

from app.config import settings
from app.models.autoresearch import (
    AgentMessage,
    AgentStreamEvent,
    DevIteration,
    ImplementationPlan,
    ReviewRound,
)
from app.services import autoresearch_project_service as project_svc
from app.services.autoresearch_agents import PlannerAgent
from app.services import autoresearch_claude_code_service as cc_svc

logger = logging.getLogger(__name__)

# ============================================================
# Event buffer system (for SSE streaming)
# ============================================================

_event_buffers: dict[str, list[AgentStreamEvent]] = {}
_event_locks: dict[str, threading.Lock] = {}
_event_locks_lock = threading.Lock()

_running: set[str] = set()
_running_lock = threading.Lock()


def _get_event_lock(project_id: str) -> threading.Lock:
    """Return a per-project lock for event buffer access, creating if needed."""
    with _event_locks_lock:
        if project_id not in _event_locks:
            _event_locks[project_id] = threading.Lock()
        return _event_locks[project_id]


def _push_event(project_id: str, event: AgentStreamEvent) -> None:
    """Append an event to the project's event buffer (thread-safe)."""
    lock = _get_event_lock(project_id)
    with lock:
        if project_id not in _event_buffers:
            _event_buffers[project_id] = []
        _event_buffers[project_id].append(event)


def get_events(project_id: str, after_index: int = 0) -> list[AgentStreamEvent]:
    """Return events from the buffer starting at *after_index*."""
    lock = _get_event_lock(project_id)
    with lock:
        buf = _event_buffers.get(project_id, [])
        return buf[after_index:]


def clear_events(project_id: str) -> None:
    """Clear the event buffer for a project."""
    lock = _get_event_lock(project_id)
    with lock:
        _event_buffers.pop(project_id, None)


def is_agent_running(project_id: str) -> bool:
    """Check whether an agent (dev or review) is currently running for this project."""
    with _running_lock:
        return project_id in _running


# ============================================================
# Git repo init
# ============================================================

def _safe_repo_name(name: str) -> str:
    """Convert a project name to a safe directory name (lowercase, hyphen-joined)."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name.strip())
    name = re.sub(r"-+", "-", name)
    return name[:80].rstrip("-")


def init_project_repo(project_id: str) -> Optional[str]:
    """Create and git-init a repo directory for the project.

    If the computed directory name already exists and belongs to a different
    project, appends ``project_id[:6]`` to disambiguate.  Updates
    ``state.project.repo_path`` via project_svc and returns the absolute path
    string, or ``None`` on error.
    """
    state = project_svc.get_project(project_id)
    if state is None:
        logger.error(f"init_project_repo: project {project_id} not found")
        return None

    # If repo already initialised, return existing path
    if state.project.repo_path:
        repo_path = Path(state.project.repo_path)
        if repo_path.exists() and (repo_path / ".git").exists():
            return str(repo_path)

    repo_name = _safe_repo_name(state.project.name)
    if not repo_name:
        repo_name = f"project-{project_id[:6]}"

    repo_path = settings.autoresearch_repos_dir / repo_name

    # Handle name collision — if the dir exists but doesn't belong to us
    if repo_path.exists():
        repo_name = f"{repo_name}-{project_id[:6]}"
        repo_path = settings.autoresearch_repos_dir / repo_name

    try:
        repo_path.mkdir(parents=True, exist_ok=True)
        if not (repo_path / ".git").exists():
            subprocess.run(
                ["git", "init"],
                cwd=str(repo_path),
                capture_output=True,
                check=True,
            )
            logger.info(f"Initialised git repo at {repo_path}")
    except Exception:
        logger.error(f"Failed to init repo at {repo_path}", exc_info=True)
        return None

    # Persist repo_path on the project state
    with project_svc._get_project_lock(project_id):
        state = project_svc.get_project(project_id)
        if state is not None:
            state.project.repo_path = str(repo_path)
            project_svc.save_state(state)

    return str(repo_path)


# ============================================================
# File generation helpers
# ============================================================

def generate_context_md(project_id: str) -> bool:
    """Write CONTEXT.md in the project repo from paper contexts."""
    state = project_svc.get_project(project_id)
    if state is None or not state.project.repo_path:
        return False

    lines: list[str] = ["# Project Context\n"]

    for ctx in state.paper_contexts:
        lines.append(f"## {ctx.title}\n")
        if ctx.content_summary:
            lines.append(f"**Summary:** {ctx.content_summary}\n")
        if ctx.key_methods:
            lines.append(f"**Key Methods:** {', '.join(ctx.key_methods)}\n")
        if ctx.key_algorithms:
            lines.append(f"**Key Algorithms:** {', '.join(ctx.key_algorithms)}\n")
        if ctx.repo_analysis:
            ra = ctx.repo_analysis
            lines.append("### Repo Analysis\n")
            if ra.structure:
                lines.append(f"- **Structure:** {ra.structure}\n")
            if ra.key_files:
                lines.append(f"- **Key Files:** {', '.join(ra.key_files)}\n")
            if ra.architecture_notes:
                lines.append(f"- **Architecture:** {ra.architecture_notes}\n")
            if ra.dependencies:
                lines.append(f"- **Dependencies:** {', '.join(ra.dependencies)}\n")
        lines.append("")

    repo_path = Path(state.project.repo_path)
    try:
        (repo_path / "CONTEXT.md").write_text("\n".join(lines), encoding="utf-8")
        return True
    except Exception:
        logger.error("Failed to write CONTEXT.md", exc_info=True)
        return False


def generate_plan_md(project_id: str) -> bool:
    """Write PLAN.md in the project repo from the implementation plan."""
    state = project_svc.get_project(project_id)
    if state is None or not state.project.repo_path or state.plan is None:
        return False

    plan = state.plan
    lines: list[str] = ["# Implementation Plan\n"]

    if plan.architecture_notes:
        lines.append(f"## Architecture\n\n{plan.architecture_notes}\n")

    if plan.dependencies:
        lines.append("## Dependencies\n")
        for dep in plan.dependencies:
            lines.append(f"- {dep}")
        lines.append("")

    if plan.modules:
        lines.append("## Modules\n")
        for mod in plan.modules:
            lines.append(f"### {mod.name}\n")
            lines.append(f"**Description:** {mod.description}\n")
            if mod.files:
                lines.append(f"**Files:** {', '.join(mod.files)}\n")
            if mod.dependencies:
                lines.append(f"**Dependencies:** {', '.join(mod.dependencies)}\n")
            lines.append(f"**Complexity:** {mod.estimated_complexity}\n")
            lines.append("")

    repo_path = Path(state.project.repo_path)
    try:
        (repo_path / "PLAN.md").write_text("\n".join(lines), encoding="utf-8")
        return True
    except Exception:
        logger.error("Failed to write PLAN.md", exc_info=True)
        return False


def generate_claude_md(project_id: str) -> bool:
    """Write CLAUDE.md in the project repo with project overview and dev guidelines."""
    state = project_svc.get_project(project_id)
    if state is None or not state.project.repo_path:
        return False

    lines: list[str] = [
        f"# {state.project.name}\n",
        f"{state.project.description}\n" if state.project.description else "",
    ]

    # Plan modules section
    if state.plan and state.plan.modules:
        lines.append("## Plan Modules\n")
        for mod in state.plan.modules:
            lines.append(f"- **{mod.name}**: {mod.description}")
        lines.append("")

    # Dev guidelines
    lines.append("## Development Guidelines\n")
    lines.append("- Python 3.12+")
    lines.append("- Use `uv` for virtual environment and dependency management")
    lines.append("- Use `pytest` for testing")
    lines.append("- Follow PEP 8 style conventions")
    lines.append("- Type hints on all public functions")
    lines.append("")

    # Testing notes
    lines.append("## Testing\n")
    lines.append("- Write unit tests for all modules")
    lines.append("- Run tests with `pytest -v`")
    lines.append("- Aim for high coverage on core logic")
    lines.append("")

    repo_path = Path(state.project.repo_path)
    try:
        (repo_path / "CLAUDE.md").write_text("\n".join(lines), encoding="utf-8")
        return True
    except Exception:
        logger.error("Failed to write CLAUDE.md", exc_info=True)
        return False


# ============================================================
# Planning phase
# ============================================================

def start_planning(project_id: str) -> dict:
    """Kick off the planning phase: init repo, generate context, assess clarity.

    Returns dict with keys ``assessment``, ``message``, ``has_plan`` (or ``error``).
    """
    try:
        # Init git repo
        repo_path = init_project_repo(project_id)
        if not repo_path:
            return {"error": "Failed to initialise project repo."}

        state = project_svc.get_project(project_id)
        if state is None:
            return {"error": "Project not found."}

        # Generate CONTEXT.md
        generate_context_md(project_id)

        # Update phase and status
        with project_svc._get_project_lock(project_id):
            state = project_svc.get_project(project_id)
            if state is None:
                return {"error": "Project not found."}
            state.project.phase = "planning_chat"
            state.project.status = "planning"
            project_svc.save_state(state)

        # Create PlannerAgent and assess clarity
        planner = PlannerAgent(
            paper_contexts=state.paper_contexts,
            project_name=state.project.name,
            project_description=state.project.description,
        )
        assessment = planner.assess_clarity()

        # Store assessment message in planning chat
        with project_svc._get_project_lock(project_id):
            state = project_svc.get_project(project_id)
            if state is None:
                return {"error": "Project not found."}
            state.planning_chat.append(AgentMessage(
                role="planner",
                content=assessment.get("message", ""),
                agent_name="planner",
            ))
            project_svc.save_state(state)

        result = {
            "assessment": assessment.get("assessment", "needs_clarification"),
            "message": assessment.get("message", ""),
            "has_plan": False,
        }

        # If scope is clear, also draft a plan
        if assessment.get("assessment") == "clear":
            plan_text, plan = planner.draft_plan()
            with project_svc._get_project_lock(project_id):
                state = project_svc.get_project(project_id)
                if state is None:
                    return {"error": "Project not found."}
                state.planning_chat.append(AgentMessage(
                    role="planner",
                    content=plan_text,
                    agent_name="planner",
                ))
                if plan is not None:
                    state.plan = plan
                    result["has_plan"] = True
                project_svc.save_state(state)

        return result

    except Exception:
        logger.error("start_planning failed", exc_info=True)
        return {"error": "An unexpected error occurred during planning setup."}


def handle_plan_chat(project_id: str, user_message: str) -> dict:
    """Handle a user message in the planning chat.

    Returns dict with ``message``, ``has_plan`` (or ``error``).
    """
    try:
        state = project_svc.get_project(project_id)
        if state is None:
            return {"error": "Project not found."}

        # Store user message
        with project_svc._get_project_lock(project_id):
            state = project_svc.get_project(project_id)
            if state is None:
                return {"error": "Project not found."}
            state.planning_chat.append(AgentMessage(
                role="user",
                content=user_message,
                agent_name="user",
            ))
            project_svc.save_state(state)

        # Build planner and chat
        planner = PlannerAgent(
            paper_contexts=state.paper_contexts,
            project_name=state.project.name,
            project_description=state.project.description,
        )

        # Re-read state to get the latest planning_chat (with user message appended)
        state = project_svc.get_project(project_id)
        if state is None:
            return {"error": "Project not found."}

        response_text, plan = planner.chat(state.planning_chat, user_message)

        # Store response
        with project_svc._get_project_lock(project_id):
            state = project_svc.get_project(project_id)
            if state is None:
                return {"error": "Project not found."}
            state.planning_chat.append(AgentMessage(
                role="planner",
                content=response_text,
                agent_name="planner",
            ))
            has_plan = False
            if plan is not None:
                state.plan = plan
                has_plan = True
            project_svc.save_state(state)

        return {"message": response_text, "has_plan": has_plan}

    except Exception:
        logger.error("handle_plan_chat failed", exc_info=True)
        return {"error": "An unexpected error occurred during planning chat."}


def approve_plan(project_id: str) -> dict:
    """Approve the current plan: mark approved, generate docs, commit to repo.

    Returns dict with ``status`` and ``repo_path`` (or ``error``).
    """
    try:
        with project_svc._get_project_lock(project_id):
            state = project_svc.get_project(project_id)
            if state is None:
                return {"error": "Project not found."}
            if state.plan is None:
                return {"error": "No plan to approve."}

            state.plan.approved = True
            state.plan.approved_at = datetime.datetime.utcnow().isoformat()
            state.project.phase = "plan_finalized"
            project_svc.save_state(state)

        # Generate PLAN.md and CLAUDE.md
        generate_plan_md(project_id)
        generate_claude_md(project_id)

        state = project_svc.get_project(project_id)
        if state is None or not state.project.repo_path:
            return {"error": "Project repo not found."}

        repo_path = state.project.repo_path

        # Git add and commit the generated files
        try:
            subprocess.run(
                ["git", "add", "CONTEXT.md", "PLAN.md", "CLAUDE.md"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Add project context, plan, and dev guidelines"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            logger.warning(f"Git commit in repo failed: {exc.stderr}")

        return {"status": "plan_finalized", "repo_path": repo_path}

    except Exception:
        logger.error("approve_plan failed", exc_info=True)
        return {"error": "An unexpected error occurred while approving the plan."}


# ============================================================
# Development cycle
# ============================================================

def _build_developer_prompt(
    state,
    review_summary: str = "",
    user_guidance: str = "",
) -> str:
    """Build the prompt sent to the Claude Code developer agent.

    First iteration: implement all modules, create venv, smoke test, commit.
    Revisions: address review findings, user guidance, update deps, run tests, commit.
    """
    iteration = state.project.current_iteration

    if iteration <= 1 and not review_summary:
        # First iteration
        module_list = ""
        if state.plan and state.plan.modules:
            for mod in state.plan.modules:
                module_list += f"- **{mod.name}**: {mod.description}"
                if mod.files:
                    module_list += f" (files: {', '.join(mod.files)})"
                module_list += "\n"

        prompt = f"""\
Implement the full project according to PLAN.md and CLAUDE.md in this repo.

## Modules to implement:
{module_list}

## Steps:
1. Read PLAN.md and CLAUDE.md for full context
2. Create a virtual environment using `uv venv` and activate it
3. Install all required dependencies with `uv pip install`
4. Implement each module as described in the plan
5. Write basic tests for core functionality
6. Run a smoke test to verify the implementation works
7. Commit all changes with a descriptive message

Focus on correctness and clean code. Follow the dev guidelines in CLAUDE.md."""

    else:
        # Revision iteration
        prompt = "Address the following review findings and improve the implementation.\n\n"

        if review_summary:
            prompt += f"## Review Findings\n{review_summary}\n\n"

        if user_guidance:
            prompt += f"## User Guidance\n{user_guidance}\n\n"

        prompt += """\
## Steps:
1. Read the review findings carefully
2. Address each finding methodically
3. Update dependencies if needed (`uv pip install`)
4. Run all tests and fix any failures
5. Commit all changes with a descriptive message

Focus on addressing the specific issues raised. Do not rewrite code unnecessarily."""

    return prompt


def start_dev_cycle(project_id: str, user_guidance: str = "") -> dict:
    """Start a development cycle in a background thread.

    Guards against duplicate runs. Streams events via the event buffer.
    Returns ``{"status": "developing"}`` or ``{"error": ...}``.
    """
    # Guard against duplicate
    with _running_lock:
        if project_id in _running:
            return {"error": "An agent is already running for this project."}
        _running.add(project_id)

    clear_events(project_id)

    def _run():
        try:
            state = project_svc.get_project(project_id)
            if state is None:
                _push_event(project_id, AgentStreamEvent(
                    event_type="error",
                    content="Project not found.",
                ))
                return

            # Build the developer prompt
            review_summary = ""
            if state.iterations:
                last_iter = state.iterations[-1]
                if last_iter.review:
                    review_summary = last_iter.review.summary

            prompt = _build_developer_prompt(state, review_summary, user_guidance)

            # Update state: status, phase, iteration
            with project_svc._get_project_lock(project_id):
                state = project_svc.get_project(project_id)
                if state is None:
                    return
                state.project.status = "developing"
                state.project.phase = "dev_cycle"
                state.project.current_iteration += 1
                current_iteration = state.project.current_iteration
                project_svc.save_state(state)

            _push_event(project_id, AgentStreamEvent(
                event_type="message",
                content=f"Starting development iteration {current_iteration}...",
                metadata={"agent": "orchestrator"},
            ))

            # Run the developer agent (async -> sync bridge)
            repo_path = state.project.repo_path
            session_id = state.project.claude_code_session_id

            loop = asyncio.new_event_loop()
            try:
                captured_session_id = None
                agent_errored = False

                async def _consume():
                    nonlocal captured_session_id
                    async for event in cc_svc.run_developer(
                        repo_path=repo_path,
                        prompt=prompt,
                        session_id=session_id,
                    ):
                        _push_event(project_id, event)
                        if event.event_type == "complete":
                            captured_session_id = event.metadata.get("session_id")
                        if event.event_type == "error" or (
                            event.event_type == "complete" and event.metadata.get("is_error")
                        ):
                            nonlocal agent_errored
                            agent_errored = True

                loop.run_until_complete(_consume())
            finally:
                loop.close()

            # If the agent errored, set project to error state
            if agent_errored:
                with project_svc._get_project_lock(project_id):
                    state = project_svc.get_project(project_id)
                    if state:
                        state.project.status = "error"
                        project_svc.save_state(state)
                return

            # Update state after completion
            with project_svc._get_project_lock(project_id):
                state = project_svc.get_project(project_id)
                if state is None:
                    return
                state.project.status = "reviewing"
                if captured_session_id:
                    state.project.claude_code_session_id = captured_session_id
                state.iterations.append(DevIteration(
                    iteration=current_iteration,
                    developer_notes=f"Development iteration {current_iteration} completed.",
                ))
                project_svc.save_state(state)

        except Exception:
            logger.error("start_dev_cycle thread failed", exc_info=True)
            _push_event(project_id, AgentStreamEvent(
                event_type="error",
                content="Development cycle failed unexpectedly.",
                metadata={"agent": "orchestrator"},
            ))
        finally:
            with _running_lock:
                _running.discard(project_id)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "developing"}


def start_review(project_id: str) -> dict:
    """Start a review cycle in a background thread.

    Returns ``{"status": "reviewing"}`` or ``{"error": ...}``.
    """
    # Guard against duplicate
    with _running_lock:
        if project_id in _running:
            return {"error": "An agent is already running for this project."}
        _running.add(project_id)

    clear_events(project_id)

    def _run():
        try:
            state = project_svc.get_project(project_id)
            if state is None:
                _push_event(project_id, AgentStreamEvent(
                    event_type="error",
                    content="Project not found.",
                ))
                return

            repo_path = state.project.repo_path
            if not repo_path:
                _push_event(project_id, AgentStreamEvent(
                    event_type="error",
                    content="Project repo path not set.",
                ))
                return

            _push_event(project_id, AgentStreamEvent(
                event_type="message",
                content="Starting code review...",
                metadata={"agent": "orchestrator"},
            ))

            description = state.project.description or state.project.name

            loop = asyncio.new_event_loop()
            review_events: list[AgentStreamEvent] = []
            review_errored = False
            try:
                async def _consume():
                    nonlocal review_errored
                    async for event in cc_svc.run_reviewer(
                        repo_path=repo_path,
                        description=description,
                    ):
                        _push_event(project_id, event)
                        review_events.append(event)
                        if event.event_type == "error" or (
                            event.event_type == "complete" and event.metadata.get("is_error")
                        ):
                            review_errored = True

                loop.run_until_complete(_consume())
            finally:
                loop.close()

            if review_errored:
                with project_svc._get_project_lock(project_id):
                    state = project_svc.get_project(project_id)
                    if state:
                        state.project.status = "error"
                        project_svc.save_state(state)
                return

            # Build review summary from captured events
            review_messages = [
                e.content for e in review_events if e.event_type == "message"
            ]
            review_summary = "\n".join(review_messages) if review_messages else "Review completed."

            # Update state after completion
            with project_svc._get_project_lock(project_id):
                state = project_svc.get_project(project_id)
                if state is None:
                    return
                state.project.status = "awaiting_user"

                # Create ReviewRound on the last iteration
                if state.iterations:
                    last_iter = state.iterations[-1]
                    last_iter.review = ReviewRound(
                        iteration=last_iter.iteration,
                        verdict="revise",  # Default; user decides
                        summary=review_summary,
                    )

                project_svc.save_state(state)

        except Exception:
            logger.error("start_review thread failed", exc_info=True)
            _push_event(project_id, AgentStreamEvent(
                event_type="error",
                content="Review cycle failed unexpectedly.",
                metadata={"agent": "orchestrator"},
            ))
        finally:
            with _running_lock:
                _running.discard(project_id)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "reviewing"}


# ============================================================
# User decision
# ============================================================

def handle_user_decision(project_id: str, decision: str, guidance: str = "") -> dict:
    """Handle user decision after review: approve, revise, or guide.

    Returns status dict or ``{"error": ...}``.
    """
    try:
        if decision == "approve":
            with project_svc._get_project_lock(project_id):
                state = project_svc.get_project(project_id)
                if state is None:
                    return {"error": "Project not found."}
                state.project.status = "complete"
                state.project.phase = "complete"
                project_svc.save_state(state)
            return {"status": "complete", "phase": "complete"}

        elif decision in ("revise", "guide"):
            return start_dev_cycle(project_id, user_guidance=guidance)

        else:
            return {"error": f"Unknown decision: {decision}"}

    except Exception:
        logger.error("handle_user_decision failed", exc_info=True)
        return {"error": "An unexpected error occurred while handling user decision."}


# ============================================================
# Utilities
# ============================================================

def get_iteration_details(project_id: str, iteration_num: int) -> Optional[dict]:
    """Return model_dump() of a specific DevIteration, or None."""
    state = project_svc.get_project(project_id)
    if state is None:
        return None
    for it in state.iterations:
        if it.iteration == iteration_num:
            return it.model_dump()
    return None


def get_project_diff(project_id: str, from_iter: int, to_iter: int) -> Optional[str]:
    """Return a git diff between two iterations.

    Uses git log to find commit hashes, then diffs between them.
    Returns the diff string or None on error.
    """
    state = project_svc.get_project(project_id)
    if state is None or not state.project.repo_path:
        return None

    repo_path = state.project.repo_path
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--reverse"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            text=True,
        )
        commits = result.stdout.strip().split("\n")
        if not commits or commits == [""]:
            return None

        # Map iteration indices to commit hashes (1-based: iteration 0 = first commit, etc.)
        # from_iter and to_iter map to commit indices
        if from_iter < 0 or to_iter < 0:
            return None
        if from_iter >= len(commits) or to_iter >= len(commits):
            return None

        from_hash = commits[from_iter].split()[0]
        to_hash = commits[to_iter].split()[0]

        diff_result = subprocess.run(
            ["git", "diff", from_hash, to_hash],
            cwd=repo_path,
            capture_output=True,
            check=True,
            text=True,
        )
        return diff_result.stdout

    except Exception:
        logger.error("get_project_diff failed", exc_info=True)
        return None
