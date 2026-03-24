# Project: ResearchClaw: Personal Research Assistant

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

## Summary and Memory Bank

- **`/Users/mbismay/Projects/researchclaw/.claude/docs/researchclaw.md`**: This is a running summary of the overall work done on the project till now. This contains crucial information, design choices, low level designs, high level design of ResearchClaw

- **`/Users/mbismay/Projects/researchclaw/docs/logs/`**: The worklog folder. This contains the work logs for every session for last 30 days. You can refer to the work logs to understand the work that was done before

- **`/Users/mbismay/.claude/projects/-Users-mbismay-Projects-researchclaw/memory/MEMORY.md`**: This is the running memory of this project. It contains key meta information like patterns, anti-patterns, correct trajectories, repititive tasks that we need to do in this project

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

## Coding Guideline

### Planning

- Always plan first. Don't assume that the first implementation would be correct. Check for upstream and downstream compatibility
- Create a well organized step-by-step plan that can be followed by a developer agent. Mention assumptions clearly.
- Plan for Edge cases.

### Development

- Always follow the pydantic structure of the repo.
- While developing, make sure that you do minimal changes to the code and repo structure to achieve the goal. Do not delete anything until absolutely necessary.
- Modify only the required file. Do not change upstream or downstream files until absolutely necessary. Always ask yourself, can the change be self-contained? If yes, then modify the concerned file
- Always make sure that upstream and downstream code flow is compatible
- If in doubt of implementation, invoke the Planner agent

### Code Review

- Once development is done, Review before proceeding further
- Review for any missed edge cases and whether development covers all Planner steps effectively
- Check for any syntax issues, upstream and downstream code compatibility issues

## Log and Summary

- Create a log file of the changes done during a session with appropriate timestamp and store it in `/Users/mbismay/Projects/researchclaw/docs/logs`
- Once a feature or set of features are developed, update `/Users/mbismay/Projects/researchclaw/docs/researchclaw.md` with relevant changes in appropriate sections only. If a section is not present, then create a new section for it.
- Update `CLAUDE.md` with crucial information which will help the agents to plan and develop better in future.
- Update the `/Users/mbismay/.claude/projects/-Users-mbismay-Projects-researchclaw/memory/MEMORY.md` with relevant meta information

## Git Rules

- Never add co-author tag in Commit messages
- Commit messages should be clean, concise and informative about the works completed since the last commit

## Notes

- No test suite exists yet
- `output/` is gitignored — contains generated papers, summaries, and explorations
- `preferences.yaml` controls which sources to crawl and what research interests to match against