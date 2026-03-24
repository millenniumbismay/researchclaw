## Goal
ResearchClaw is an end-to-end research assistant starting from research paper crawling to autoresearch. An academic researcher is our target user. The workflow looks broadly like: A researcher provides a research topic or domain of research they are interested in -> ResearchClaw crawls related papers everyday and present them with confidence and tags -> Researcher add few of those papers to their list (My List) -> They further explores a paper which is closely aligned with their research interests -> ResearchClaw help in Literature Survey, finds related papers and discusses with the Researcher in identifying gaps in current research and creating and refining research directions -> Once a few research directions are identified, a basic implementation of the code and experiments are done completely autonomously by ResearchClaw and will be further iterated with the researcher -> Finally researcher and ResearchClaw iteratively perform autoresearch in multiple direction with an aim to close the gaps and explore experiments to consolidate the research directions.

## Quick Start

```bash
conda activate ar # Activate conda env
./run.sh          # one-shot crawl + summarize
./start_ui.sh     # web UI at http://localhost:7337
```

## Key Commands

- `python crawl.py` — fetch and classify papers from configured sources
- `python summarize.py` — generate summaries + send Telegram notifications
- `uvicorn app:app --port 7337` — start web server
- `./run.sh` — crawl + summarize in one shot
- `./start_ui.sh` — launch web UI

## Architecture

- **Backend:** FastAPI with Pydantic models, service layer pattern
- **Frontend:** Vanilla JS + D3.js + Chart.js (no framework)
- **Entry points:** `app.py` / `ui.py` (web), `crawl.py` (data pipeline), `summarize.py` (AI summaries)
- **Models:** `app/models/` — Pydantic data models
- **Routes:** `app/routes/` — API endpoints (thin, delegate to services)
- **Services:** `app/services/` — business logic
- **Static:** `static/css/` and `static/js/` — modular CSS and JS files

## Conventions

- Python: `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants
- Services own business logic; route handlers are thin wrappers that delegate to services
- JSON files for state: `papers_cache.json`, `filtered_papers.json`, `mylist.json`, `feedback.json`
- Paper markdown files use YAML frontmatter for metadata
- Safe filenames via `_safe_filename()` — lowercase, strip special chars, hyphen-joined
- Claude model: `claude-haiku-4-5` (defined as `MODEL` constant in scripts)
- Background tasks (crawls) run in daemon threads via `threading`

## Environment Variables (.env)

- `ANTHROPIC_API_KEY` — required for Claude API
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — for notification delivery
- `TWITTER_BEARER_TOKEN` — optional, for Twitter/X paper source

## Git Rules

- Never add co-author tag in Commit messages


## Important Notes

- No test suite exists yet
- `output/` is gitignored — contains generated papers, summaries, and explorations
- `preferences.yaml` controls which sources to crawl and what research interests to match against
