"""AutoResearch Agents — Planner agent for Phase B planning chat."""

import json
import logging
import os
import re
from typing import Optional

import anthropic

from app.models.autoresearch import (
    AgentMessage,
    ImplementationPlan,
    PaperContext,
    PlanModule,
)

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-6"


class PlannerAgent:
    """Conversational planner that turns paper context into an implementation plan.

    The Planner runs as a multi-turn chat via the Anthropic SDK.  It ingests
    paper contexts (summaries, methods, repo analyses) and, through
    conversation with the user, produces a structured ImplementationPlan.
    """

    def __init__(
        self,
        paper_contexts: list[PaperContext],
        project_name: str,
        project_description: str = "",
    ) -> None:
        self.paper_contexts = paper_contexts
        self.project_name = project_name
        self.project_description = project_description
        self.model = MODEL
        self.client = anthropic.Anthropic()

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
    # Assess clarity
    # ------------------------------------------------------------------

    def _system_with_cache(self) -> list[dict]:
        """Return the system prompt as a cacheable content block."""
        return [
            {
                "type": "text",
                "text": self._build_system_prompt(),
                "cache_control": {"type": "ephemeral"},
            }
        ]

    @staticmethod
    def _merge_consecutive_roles(messages: list[dict]) -> list[dict]:
        """Merge consecutive messages with the same role to satisfy API contract.

        The Anthropic API requires strictly alternating user/assistant roles.
        If consecutive messages share a role, their content is joined with newlines.
        """
        if not messages:
            return messages
        merged: list[dict] = [messages[0].copy()]
        for msg in messages[1:]:
            if msg["role"] == merged[-1]["role"]:
                prev_content = merged[-1]["content"]
                cur_content = msg["content"]
                # Handle both str and list content formats
                if isinstance(prev_content, str) and isinstance(cur_content, str):
                    merged[-1]["content"] = prev_content + "\n\n" + cur_content
                else:
                    merged[-1]["content"] = str(prev_content) + "\n\n" + str(cur_content)
            else:
                merged.append(msg.copy())
        return merged

    def assess_clarity(self) -> dict:
        """Single LLM call to assess whether the project scope is clear enough to plan.

        Returns:
            dict with keys "assessment" ("clear" | "needs_clarification") and "message".
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set — returning needs_clarification fallback")
            return {
                "assessment": "needs_clarification",
                "message": "API key is not configured. Please set ANTHROPIC_API_KEY to enable the planner.",
            }

        system = self._system_with_cache()
        messages = [
            {
                "role": "user",
                "content": (
                    "Based on the project description and paper context above, "
                    "assess whether there is enough information to draft an implementation plan. "
                    'Respond with a JSON object: {"assessment": "clear" or "needs_clarification", '
                    '"message": "your explanation"}. '
                    "Only output the JSON, no other text."
                ),
            }
        ]

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system,
                messages=messages,
            )
            text = response.content[0].text.strip()

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
            logger.error("assess_clarity LLM call failed", exc_info=True)
            return {
                "assessment": "needs_clarification",
                "message": "Failed to assess project clarity due to an internal error. Please try again.",
            }

    # ------------------------------------------------------------------
    # Draft plan
    # ------------------------------------------------------------------

    def draft_plan(self, user_requirements: str = "") -> tuple[str, Optional[ImplementationPlan]]:
        """Generate an implementation plan in a single LLM call.

        Args:
            user_requirements: Optional additional requirements from the user.

        Returns:
            Tuple of (assistant_text, ImplementationPlan or None).
        """
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return "Cannot generate plan without ANTHROPIC_API_KEY.", None

        system = self._system_with_cache()

        prompt = "Please draft an implementation plan for this project."
        if user_requirements:
            prompt += f"\n\nAdditional requirements from the user:\n{user_requirements}"

        messages = [{"role": "user", "content": prompt}]

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=messages,
            )
            text = response.content[0].text
            plan = self._extract_plan(text)
            return text, plan

        except Exception:
            logger.error("draft_plan LLM call failed", exc_info=True)
            return "Failed to generate a plan due to an internal error. Please try again.", None

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def chat(
        self,
        history: list[AgentMessage],
        user_message: str,
    ) -> tuple[str, Optional[ImplementationPlan]]:
        """Continue the planning conversation.

        Builds the message list from history (mapping planner -> assistant role)
        and appends the current user message.

        Args:
            history: Previous AgentMessage objects from the planning chat.
            user_message: The latest message from the user.

        Returns:
            Tuple of (assistant_text, ImplementationPlan or None).
        """
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return "Cannot chat without ANTHROPIC_API_KEY.", None

        system = self._system_with_cache()

        messages: list[dict] = []
        for msg in history:
            if msg.role == "user":
                role = "user"
            else:
                # planner, system, or any other role maps to assistant
                role = "assistant"
            messages.append({"role": role, "content": msg.content})

        messages.append({"role": "user", "content": user_message})

        # Merge consecutive same-role messages (e.g. back-to-back planner messages)
        # to satisfy the Anthropic API alternating-role requirement
        messages = self._merge_consecutive_roles(messages)

        # Mark the second-to-last message for prompt caching so the growing
        # conversation prefix is cached across turns
        if len(messages) >= 2:
            cache_msg = messages[-2]
            content = cache_msg["content"]
            if isinstance(content, str):
                cache_msg["content"] = [
                    {"type": "text", "text": content, "cache_control": {"type": "ephemeral"}}
                ]

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                messages=messages,
            )
            text = response.content[0].text
            plan = self._extract_plan(text)
            return text, plan

        except Exception:
            logger.error("chat LLM call failed", exc_info=True)
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
