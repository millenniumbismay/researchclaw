# Planner SDK Refactor

**Date:** 2026-04-10
**Branch:** `planner_sdk_refactor_2026-04-10` (merged to `main`)

## Summary

Refactored all AutoResearch LLM calls from the raw Anthropic SDK to `claude-agent-sdk`, eliminating the need for a separate `ANTHROPIC_API_KEY` and routing everything through the user's existing Claude subscription at no extra API cost.

## Changes

### Modified Files
- `app/services/autoresearch_agents.py` — Complete rewrite of PlannerAgent: removed `anthropic` import, `_system_with_cache()`, `_merge_consecutive_roles()`, all `ANTHROPIC_API_KEY` checks. Added async methods using `claude_agent_sdk.query()` with `allowed_tools=[]` for pure chat, session resumption via `resume=session_id`.
- `app/services/autoresearch_context_service.py` — Replaced `_extract_paper_context_with_llm` and `_analyze_repo_with_llm` to use `_llm_query_sync()` helper (claude-agent-sdk via `asyncio.run()` bridge for background threads). Removed `import anthropic` and all API key checks.
- `app/services/autoresearch_orchestrator.py` — `start_planning()` and `handle_plan_chat()` changed to `async def`. Planning session_id saved/loaded from state. Chat no longer passes message history (SDK manages it via session).
- `app/routes/autoresearch.py` — Added `await` to `start_planning_route` and `plan_chat` route handlers.
- `app/models/autoresearch.py` — Added `planning_session_id: Optional[str] = None` to `AutoResearchProject`.
- `app/services/autoresearch_claude_code_service.py` — Added `env={"ANTHROPIC_API_KEY": ""}` to all `ClaudeAgentOptions` to prevent invalid key interference.
- `app/main.py` — Added `python-dotenv` loading at startup.
- `requirements.txt` — Added `python-dotenv>=1.0.0`.

## Bugs Found & Fixed

- **ANTHROPIC_API_KEY poisoning SDK auth**: An invalid `ANTHROPIC_API_KEY` loaded from `.env` was being inherited by the `claude` CLI subprocess, causing it to fail with exit code 1 instead of using its own OAuth auth. Fixed by explicitly unsetting the key in SDK `env` options: `env={"ANTHROPIC_API_KEY": ""}`.
- **Context builder arXiv fallback**: Papers added via `fetch_paper_by_url` weren't persisted to the papers cache, causing `get_paper_by_id()` to return None in the context builder. Fixed by falling back to `fetch_paper_by_url()` when paper_id starts with `arxiv:`.
- **Server not loading .env**: The uvicorn process didn't source `.env` automatically. Fixed by adding `python-dotenv` loading in `app/main.py`.

## Design Decisions
- **claude-agent-sdk with `allowed_tools=[]`** — pure text generation, same auth as Claude Code
- **Session resumption for multi-turn planning** — SDK manages conversation history internally, eliminating manual message history management, consecutive-role merging, and prompt caching code
- **`asyncio.run()` in background threads** — context service LLM calls run in daemon threads (no event loop), so `asyncio.run()` is safe
- **Explicit env override** — `env={"ANTHROPIC_API_KEY": ""}` prevents stale/invalid keys from interfering with SDK's OAuth auth

## E2E Verification
1. Context build: populated methods (7) and algorithms (5) for "Are Latent Reasoning Models Easily Interpretable?"
2. Planning: assess_clarity returned structured response, chat with session resumption worked across turns
3. Planner autonomously fetched the full paper to read methodology details

## Commits (2)
1. `6d191ee` — Add dotenv loading, fix context builder arXiv fallback, update docs
2. `00b15e9` — Refactor planner and context LLM calls from Anthropic SDK to claude-agent-sdk
