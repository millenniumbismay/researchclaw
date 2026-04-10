# ResearchClaw — Project Summary

> Running summary of project state, features, and session work. Update after each session.

## Current State

- **Branch:** `autoresearch_phase_b_2026-04-09` (pending merge to `main`)
- **Last updated:** 2026-04-09
- **Stack:** FastAPI + Pydantic (backend), Vanilla JS + D3.js + Chart.js (frontend)
- **Test suite:** None yet
- **Deployment:** Local only (`localhost:7337`)

## Feature Map

| Feature | Status | Key Files |
|---------|--------|-----------|
| Paper crawling (arXiv, Twitter, custom) | Done | `crawl.py`, `preferences.yaml` |
| AI summaries + Telegram notifications | Done | `summarize.py` |
| Web UI — Dashboard with confidence/tags | Done | `app/routes/papers.py`, `static/js/papers.js` |
| Web UI — My List management | Done | `app/routes/feedback.py`, `static/js/mylist.js` |
| Web UI — Explorations tab (3-pane) | Done | `app/routes/explorations.py`, `static/js/explorations.js` |
| 3-hop knowledge graph (D3) | Done | `app/services/literature_survey_service.py`, `static/js/literature_survey.js` |
| Richer edges (commonalities + differences) | Done | same as above |
| Original Related Works (arXiv HTML) | Done | `app/services/paper_content_service.py` |
| Paper content fetch + cache on My List add | Done | `app/services/paper_content_service.py`, `app/routes/feedback.py` |
| Graph staleness detection + regenerate | Done | `app/services/literature_survey_service.py` |
| Frontend redesign (dark/light/system themes) | Done | `static/js/theme.js`, all CSS files, `templates/index.html` |
| Sidebar navigation | Done | `templates/index.html`, `static/css/base.css`, `static/js/app.js` |
| Research Directions | Done | `static/js/research_directions.js`, `app/routes/explorations.py` |
| AutoResearch — Tab + project management + context pipeline | Done | `app/routes/autoresearch.py`, `app/services/autoresearch_*`, `static/js/autoresearch.js` |
| AutoResearch — Multi-agent dev loop (plan → dev → review) | Done | `app/services/autoresearch_agents.py`, `autoresearch_orchestrator.py`, `autoresearch_claude_code_service.py` |

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| Service layer pattern | Routes stay thin; business logic is testable and reusable |
| Vanilla JS (no React/Vue) | Lightweight, no build step, fast iteration |
| JSON files for state (not DB) | Simple for single-user local tool; easy to inspect/debug |
| Background daemon threads | Avoid blocking UI for slow operations (arXiv fetch, Claude API calls) |
| Batched Claude API calls | 5 paper pairs per call reduces cost ~5x vs per-pair |
| arXiv HTML extraction + sanitization | Get original Related Work section; sanitize to prevent XSS |
| `claude-haiku-4-5` for all automated calls | Cost-efficient for high-volume operations |
| Anthropic SDK for planning, Claude Agent SDK for dev/review | Right tool for each: chat vs filesystem agent |
| Prompt caching on system + history prefix | Reduces cost for multi-turn planning with large paper contexts |
| Standalone git repos per AutoResearch project | Isolation between experiments; `uv` for fast venv |
| SSE for agent activity streaming | Simpler than WebSocket for unidirectional server→client events |

## Session Log

<!-- Add new sessions at the top. Keep entries concise. -->

### 2026-04-09 — AutoResearch Phase A + B

**Branch:** `autoresearch_phase_a_2026-04-09` → `autoresearch_phase_b_2026-04-09`

**What was done:**
- Phase A: AutoResearch tab, project CRUD, paper selection (MyList + arXiv URL), GitHub repo cloning/analysis, LLM-powered context extraction pipeline
- Phase B: PlannerAgent (Anthropic SDK, Opus 4.6) with prompt caching, Claude Code developer/reviewer agents, orchestrator state machine (planning → dev → review → user decision loop), SSE streaming, full frontend UI for all phases
- Adversarial review (Critic/Tester/Advocate/Judge) caught 10 issues, all fixed: max_iterations enforcement, consecutive same-role message merging, delete guards, URL validation, context merge, SSE timeout, phase guards

**Key files created:**
- `app/services/autoresearch_agents.py`, `autoresearch_claude_code_service.py`, `autoresearch_orchestrator.py`
- `app/services/autoresearch_project_service.py`, `autoresearch_context_service.py`
- `app/models/autoresearch.py`, `app/routes/autoresearch.py`
- `static/js/autoresearch.js`, `static/css/autoresearch.css`

---

### 2026-04-08 — Frontend Redesign

**Branch:** `frontend_redesign_2026-04-08`

**What was done:**
- Complete CSS-first frontend redesign: purple/lilac/blue/black color scheme
- Dark + Light + System theme toggle with localStorage persistence (`theme.js`)
- Sidebar navigation replacing horizontal tab bar, collapsible on mobile
- 3-state paper cards: flat default → subtle border on hover → full accent on expand
- All 7 CSS files rewritten with CSS custom properties for theming
- Chart colors changed to distinct amber/purple/emerald for readability
- Assistant tab with dedicated chat UI and prompt tiles
- Backward-compat `--muted` alias kept for JS inline styles

**Key files created/modified:**
- NEW: `static/js/theme.js`, `static/css/assistant.css`, `static/js/assistant.js`
- Modified: `templates/index.html` (sidebar nav restructure)
- Modified: `static/js/app.js` (sidebar-aware tab switching)
- Modified: `static/js/dashboard.js` (card expand classes, chart colors)
- Rewritten: `base.css`, `components.css`, `dashboard.css`, `mylist.css`, `explorations.css`, `settings.css`, `assistant.css`

---

### 2026-03-24 — Knowledge Graph Improvements

**Branch:** `knowledge_graph` → merged to `main`

**What was done:**
- Explore-only left pane: only papers where user clicked "Explore" appear (not all My List)
- 3-hop knowledge graph with controlled fan-out (6→3→2, ~30-40 nodes)
- Richer edges: commonalities + differences via batched Claude API calls
- Replaced AI-generated literature survey with original Related Work section from arXiv HTML
- Paper content fetching + caching service (`paper_content_service.py`)
- Graph staleness detection when My List changes
- Renamed "Literature Survey" → "Related Works" throughout UI
- Visual refinements: dark lilac focal node, increased edge visibility

**Key files created/modified:**
- NEW: `app/services/paper_content_service.py`
- Modified: `app/services/literature_survey_service.py` (major rewrite)
- Modified: `app/models/literature_survey.py` (hop_level, commonalities, differences, related_work_html)
- Modified: `static/js/literature_survey.js` (multi-hop D3 viz, legend, tooltips)
- Modified: `static/js/explorations.js`, `api.js`, `state.js`, `app.js`, `mylist.js`

**Issues found & fixed:**
- XSS vulnerability: raw arXiv HTML injected via innerHTML → added `_sanitize_html()`
- Staleness check: focal paper extracted mid-loop → moved before loop
- Timestamp comparison: tz-aware vs naive datetime → normalized both
- Stale "Untitled" exploration folders → filtered in API + deleted from disk

---

### 2026-03-23 — Modular Architecture + Explorations Tab

**Branch:** `main`

**What was done:**
- Refactored monolithic `app.py` into modular architecture (models/, routes/, services/)
- Added Explorations tab with 3-pane layout
- Initial 1-hop knowledge graph with D3.js
- AI-generated literature survey text
- Copy related papers to exploration folder
- Foldable middle pane sections (Literature Survey + Research Directions)

---

### 2026-03-22 — Initial Release

**Branch:** `main`

**What was done:**
- Paper crawling from arXiv and configurable sources
- AI-powered classification with confidence scores and tags
- Web UI dashboard with paper cards showing abstracts
- My List for saving papers of interest
- Telegram notification delivery
- Demo video/GIF for README

## Tech Debt / Known Issues

- No test suite
- No authentication (single-user local tool assumption)
- Survey generation is synchronous within the background thread (no progress reporting)
- Rate limiting is per-process only (no cross-process coordination for arXiv)
- Old exploration folders without `title` in meta.json are silently filtered out
