# ResearchClaw

AI-powered research paper curator. Crawls arXiv, Semantic Scholar, and HuggingFace Daily Papers, then uses Claude to classify and summarize relevant papers. FastAPI web UI with D3 knowledge graphs.

## Quick Start

```bash
conda activate ar
pip install -r requirements.txt
# Create .env with ANTHROPIC_API_KEY (required), TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
# Edit preferences.yaml for research interests
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

## Important Notes

- No test suite exists yet
- `output/` is gitignored — contains generated papers, summaries, and explorations
- `preferences.yaml` controls which sources to crawl and what research interests to match against
