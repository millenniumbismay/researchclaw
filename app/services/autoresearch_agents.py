"""AutoResearch Agents — Planner agent for Phase B planning chat.

Uses claude-agent-sdk (same auth as Claude Code) instead of the raw Anthropic SDK,
so all LLM calls go through the user's existing Claude subscription.
"""

import json
import logging
import re
from typing import Optional

from app.models.autoresearch import (
    ImplementationPlan,
    PaperContext,
    PlanModule,
)

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-6"


class PlannerAgent:
    """Conversational planner that turns paper context into an implementation plan.

    Uses claude-agent-sdk with allowed_tools=[] for pure text generation.
    Multi-turn conversation state is managed by the SDK via session resumption.
    """

    def __init__(
        self,
        paper_contexts: list[PaperContext],
        project_name: str,
        project_description: str = "",
        session_id: Optional[str] = None,
    ) -> None:
        self.paper_contexts = paper_contexts
        self.project_name = project_name
        self.project_description = project_description
        self.model = MODEL
        self.session_id = session_id

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        """Build a system prompt that includes all paper/repo context."""

        paper_sections: list[str] = []
        for ctx in self.paper_contexts:
            section = f"### Paper: {ctx.title} (ID: {ctx.paper_id})\n"
            if ctx.content_summary:
                section += f"**Summary:** {ctx.content_summary}\n"
            if ctx.key_methods:
                section += f"**Key Methods:** {', '.join(ctx.key_methods)}\n"
            if ctx.key_algorithms:
                section += f"**Key Algorithms:** {', '.join(ctx.key_algorithms)}\n"
            if ctx.github_repo_url:
                section += f"**GitHub Repo:** {ctx.github_repo_url}\n"
            if ctx.repo_analysis:
                ra = ctx.repo_analysis
                section += "**Repo Analysis:**\n"
                if ra.structure:
                    section += f"  - Structure: {ra.structure}\n"
                if ra.key_files:
                    section += f"  - Key Files: {', '.join(ra.key_files)}\n"
                if ra.architecture_notes:
                    section += f"  - Architecture: {ra.architecture_notes}\n"
                if ra.dependencies:
                    section += f"  - Dependencies: {', '.join(ra.dependencies)}\n"
                if ra.language_breakdown:
                    langs = ", ".join(
                        f"{lang}: {pct:.0f}%" for lang, pct in ra.language_breakdown.items()
                    )
                    section += f"  - Languages: {langs}\n"
            paper_sections.append(section)

        papers_block = "\n".join(paper_sections) if paper_sections else "(No papers provided yet.)"

        return f"""\
You are PlannerAgent, an expert software architect specializing in turning \
research papers into working implementations.

## Project
- **Name:** {self.project_name}
- **Description:** {self.project_description or "(not provided)"}

## Paper Context
{papers_block}

## Your Role
1. Understand the research ideas, methods, and algorithms from the papers above.
2. Through conversation with the user, clarify requirements and scope.
3. Produce a concrete implementation plan broken into modules.

## Plan Format
When you have enough information to produce a plan, output it as a JSON block \
inside triple-backtick json fences. The JSON must conform to this schema:

```json
{{
  "modules": [
    {{
      "name": "module_name",
      "description": "What this module does",
      "files": ["path/to/file.py"],
      "dependencies": ["other_module"],
      "estimated_complexity": "low | medium | high"
    }}
  ],
  "architecture_notes": "High-level architecture description",
  "dependencies": ["external_package_1", "external_package_2"]
}}
```

## Guidelines
- Ask clarifying questions if the scope or requirements are unclear.
- Break the implementation into small, well-defined modules.
- Identify external dependencies (pip packages, APIs, etc.).
- Consider error handling, testing, and edge cases.
- Be specific about file paths and module boundaries.
- Only produce the plan JSON when you are confident the requirements are clear."""

    # ------------------------------------------------------------------
    # SDK helper
    # ------------------------------------------------------------------

    async def _query_sdk(self, prompt: str, use_system: bool = False) -> tuple[str, Optional[str]]:
        """Run a query through claude-agent-sdk and collect text output.

        Args:
            prompt: The user prompt to send.
            use_system: If True, include system_prompt (for first call in session).

        Returns:
            Tuple of (collected_text, session_id).
        """
        from claude_agent_sdk import ClaudeAgentOptions, query
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

        def _log_stderr(line: str) -> None:
            logger.debug(f"planner sdk stderr: {line}")

        # Prevent an invalid ANTHROPIC_API_KEY in the environment from
        # overriding the SDK's own OAuth auth by explicitly unsetting it.
        sdk_env = {"ANTHROPIC_API_KEY": ""}

        options = ClaudeAgentOptions(
            allowed_tools=[],
            model=self.model,
            stderr=_log_stderr,
            env=sdk_env,
        )

        if self.session_id:
            options.resume = self.session_id
        elif use_system:
            options.system_prompt = self._build_system_prompt()

        text_parts: list[str] = []
        captured_session_id: Optional[str] = None

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                captured_session_id = getattr(message, "session_id", None)
                if getattr(message, "is_error", False):
                    logger.error(f"SDK query returned error for planner")

        return "".join(text_parts), captured_session_id

    # ------------------------------------------------------------------
    # Assess clarity
    # ------------------------------------------------------------------

    async def assess_clarity(self) -> dict:
        """Single LLM call to assess whether the project scope is clear enough to plan.

        Returns:
            dict with keys "assessment" ("clear" | "needs_clarification") and "message".
        """
        prompt = (
            "Based on the project description and paper context above, "
            "assess whether there is enough information to draft an implementation plan. "
            'Respond with a JSON object: {"assessment": "clear" or "needs_clarification", '
            '"message": "your explanation"}. '
            "Only output the JSON, no other text."
        )

        try:
            text, session_id = await self._query_sdk(prompt, use_system=True)
            if session_id:
                self.session_id = session_id

            text = text.strip()

            # Try to parse the response as JSON directly
            try:
                result = json.loads(text)
                if "assessment" in result and "message" in result:
                    return result
            except json.JSONDecodeError:
                pass

            # Fallback: extract JSON from fenced block
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                result = json.loads(match.group(1))
                if "assessment" in result and "message" in result:
                    return result

            # If we can't parse, treat the whole text as the message
            return {"assessment": "needs_clarification", "message": text}

        except Exception:
            logger.error("assess_clarity SDK call failed", exc_info=True)
            return {
                "assessment": "needs_clarification",
                "message": "Failed to assess project clarity due to an internal error. Please try again.",
            }

    # ------------------------------------------------------------------
    # Draft plan
    # ------------------------------------------------------------------

    async def draft_plan(self, user_requirements: str = "") -> tuple[str, Optional[ImplementationPlan]]:
        """Generate an implementation plan via the SDK.

        Args:
            user_requirements: Optional additional requirements from the user.

        Returns:
            Tuple of (assistant_text, ImplementationPlan or None).
        """
        prompt = "Please draft an implementation plan for this project."
        if user_requirements:
            prompt += f"\n\nAdditional requirements from the user:\n{user_requirements}"

        try:
            text, session_id = await self._query_sdk(prompt)
            if session_id:
                self.session_id = session_id

            plan = self._extract_plan(text)
            return text, plan

        except Exception:
            logger.error("draft_plan SDK call failed", exc_info=True)
            return "Failed to generate a plan due to an internal error. Please try again.", None

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    async def chat(self, user_message: str) -> tuple[str, Optional[ImplementationPlan]]:
        """Continue the planning conversation via session resumption.

        The SDK maintains full conversation history internally via the session.
        No need to pass message history — just resume and send the new message.

        Args:
            user_message: The latest message from the user.

        Returns:
            Tuple of (assistant_text, ImplementationPlan or None).
        """
        try:
            text, session_id = await self._query_sdk(user_message)
            if session_id:
                self.session_id = session_id

            plan = self._extract_plan(text)
            return text, plan

        except Exception:
            logger.error("chat SDK call failed", exc_info=True)
            return "Failed to process your message due to an internal error. Please try again.", None

    # ------------------------------------------------------------------
    # Plan extraction
    # ------------------------------------------------------------------

    def _extract_plan(self, text: str) -> Optional[ImplementationPlan]:
        """Extract an ImplementationPlan from a ```json fenced block in LLM output.

        Searches for JSON blocks that contain a "modules" key and attempts to
        parse them into an ImplementationPlan.

        Returns:
            ImplementationPlan if a valid plan JSON was found, else None.
        """
        # Find all ```json ... ``` blocks
        pattern = r"```json\s*(.*?)\s*```"
        matches = re.findall(pattern, text, re.DOTALL)

        for block in matches:
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue

            # Must have a "modules" key to be considered a plan
            if not isinstance(data, dict) or "modules" not in data:
                continue

            try:
                modules = [PlanModule(**m) for m in data.get("modules", [])]
                plan = ImplementationPlan(
                    modules=modules,
                    architecture_notes=data.get("architecture_notes", ""),
                    dependencies=data.get("dependencies", []),
                )
                return plan
            except Exception:
                logger.warning("Found JSON block with 'modules' but failed to parse as plan", exc_info=True)
                continue

        return None
