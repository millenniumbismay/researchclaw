"""AutoResearch Claude Code Service — thin async wrapper around claude-agent-sdk.

Spawns Developer and Reviewer agents via Claude Code subprocess,
converting SDK messages into AgentStreamEvent objects for SSE streaming.
"""

import datetime
import logging
from typing import AsyncIterator

from app.models.autoresearch import AgentStreamEvent

logger = logging.getLogger(__name__)

# Max chars for tool result content in the stream
_TOOL_RESULT_MAX_CHARS = 500


# ============================================================
# Developer agent
# ============================================================

async def run_developer(
    repo_path: str,
    prompt: str,
    session_id: str | None = None,
) -> AsyncIterator[AgentStreamEvent]:
    """Run the Developer agent via Claude Code SDK.

    Yields AgentStreamEvent objects suitable for SSE streaming.
    If session_id is provided, resumes an existing Claude Code session.
    """
    from claude_agent_sdk import ClaudeAgentOptions, query

    try:
        options = ClaudeAgentOptions(
            cwd=repo_path,
            allowed_tools=["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
            permission_mode="acceptEdits",
            model="claude-opus-4-6",
        )

        if session_id:
            options.resume = session_id

        async for message in query(prompt=prompt, options=options):
            for event in _message_to_events(message, agent_name="developer"):
                yield event

    except Exception as exc:
        logger.error(f"Developer agent error: {exc}", exc_info=True)
        yield AgentStreamEvent(
            event_type="error",
            content=str(exc),
            timestamp=datetime.datetime.utcnow().isoformat(),
            metadata={"agent": "developer"},
        )


# ============================================================
# Reviewer agent
# ============================================================

async def run_reviewer(
    repo_path: str,
    description: str,
) -> AsyncIterator[AgentStreamEvent]:
    """Run the Reviewer agent via Claude Code SDK.

    Uses the /adversarial-review skill to dispatch Critic, Tester, and
    Advocate sub-agents in parallel, then a Judge classifies findings.
    """
    from claude_agent_sdk import ClaudeAgentOptions, query

    try:
        review_prompt = f'/adversarial-review "{description}"'

        options = ClaudeAgentOptions(
            cwd=repo_path,
            allowed_tools=["Read", "Edit", "Write", "Bash", "Glob", "Grep", "Agent"],
            permission_mode="acceptEdits",
            model="claude-opus-4-6",
        )

        async for message in query(prompt=review_prompt, options=options):
            for event in _message_to_events(message, agent_name="reviewer"):
                yield event

    except Exception as exc:
        logger.error(f"Reviewer agent error: {exc}", exc_info=True)
        yield AgentStreamEvent(
            event_type="error",
            content=str(exc),
            timestamp=datetime.datetime.utcnow().isoformat(),
            metadata={"agent": "reviewer"},
        )


# ============================================================
# Message -> Event conversion
# ============================================================

def _message_to_events(message, agent_name: str) -> list[AgentStreamEvent]:
    """Convert a claude-agent-sdk message into a list of AgentStreamEvent objects.

    Handles:
    - AssistantMessage: iterate content blocks (TextBlock, ToolUseBlock, ToolResultBlock)
    - ResultMessage: extract completion metadata (session_id, duration, cost, turns, errors)
    """
    from claude_agent_sdk import (
        AssistantMessage,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
        ToolResultBlock,
    )

    events: list[AgentStreamEvent] = []
    now = datetime.datetime.utcnow().isoformat()

    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                events.append(AgentStreamEvent(
                    event_type="message",
                    content=block.text,
                    timestamp=now,
                    metadata={"agent": agent_name},
                ))
            elif isinstance(block, ToolUseBlock):
                summary = _summarize_tool_input(block.name, block.input)
                events.append(AgentStreamEvent(
                    event_type="tool_use",
                    content=summary,
                    timestamp=now,
                    metadata={
                        "agent": agent_name,
                        "tool_name": block.name,
                        "tool_id": block.id,
                    },
                ))
            elif isinstance(block, ToolResultBlock):
                # Truncate long tool results for the stream
                content = str(block.content) if block.content else ""
                if len(content) > _TOOL_RESULT_MAX_CHARS:
                    content = content[:_TOOL_RESULT_MAX_CHARS] + "..."
                events.append(AgentStreamEvent(
                    event_type="tool_result",
                    content=content,
                    timestamp=now,
                    metadata={
                        "agent": agent_name,
                        "tool_id": getattr(block, "tool_use_id", ""),
                    },
                ))

    elif isinstance(message, ResultMessage):
        is_error = getattr(message, "is_error", False)
        events.append(AgentStreamEvent(
            event_type="error" if is_error else "complete",
            content="Agent run failed." if is_error else "Agent run completed.",
            timestamp=now,
            metadata={
                "agent": agent_name,
                "session_id": getattr(message, "session_id", None),
                "duration_ms": getattr(message, "duration_ms", None),
                "cost_usd": getattr(message, "total_cost_usd", None),
                "num_turns": getattr(message, "num_turns", None),
                "is_error": is_error,
            },
        ))

    return events


# ============================================================
# Tool input summarization
# ============================================================

def _summarize_tool_input(tool_name: str, tool_input: dict) -> str:
    """Produce a concise one-line summary of a tool invocation for the event stream."""
    if not isinstance(tool_input, dict):
        return str(tool_input)[:100]

    if tool_name == "Read":
        return tool_input.get("file_path", str(tool_input)[:100])

    if tool_name in ("Edit", "Write"):
        return tool_input.get("file_path", str(tool_input)[:100])

    if tool_name == "Bash":
        cmd = tool_input.get("command", str(tool_input)[:120])
        return cmd[:120]

    if tool_name in ("Glob", "Grep"):
        return tool_input.get("pattern", str(tool_input)[:100])

    # Fallback for unknown tools
    return str(tool_input)[:100]
