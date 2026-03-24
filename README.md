# 🦞 ResearchClaw

> **Your personal AI-powered research paper curator.** Set your interests once, get a daily digest of the most relevant papers — tagged, scored, and summarized by Claude. Explore connections between papers with interactive knowledge graphs and AI-generated literature surveys.

![ResearchClaw Demo](assets/demo.gif)

---

## What it does

ResearchClaw automatically discovers, filters, and summarizes research papers from multiple sources every day. It's built around one idea: **you should only read papers that actually matter to you**, and you shouldn't have to spend an hour on arXiv to find them.

Every evening at 8pm, it:

1. **Crawls** arXiv, Semantic Scholar, and HuggingFace Daily Papers
2. **Classifies** each paper using Claude Haiku — assigns tags from your interest list and a confidence score (1–5)
3. **Filters** to only papers with confidence ≥ 3
4. **Fetches full paper text** from arXiv HTML for rich, accurate summaries
5. **Auto-summarizes** papers with confidence = 5 using structured prompts (Abstract, Introduction Highlights, Research Questions, Methodology & Key Findings)
6. **Notifies** you on Telegram with the top papers of the day
7. **Serves** a local web dashboard where you can browse, save, explore, and annotate everything

---

## The Dashboard

A dark-mode web UI (FastAPI + vanilla JS) with four tabs:

### 📊 Dashboard
- **Stacked bar chart** — papers crawled per day, broken down by confidence level (3/4/5) over the last 90 days
- **Paper feed** — grouped by date, with tag chips, confidence badges, and source labels
- **One-click actions** — "+ My List" to save, "✕ Not Relevant" to dismiss (and delete the files)
- **Expandable abstract** — click "▼ Abstract" on any card to read the full abstract inline
- **Expandable summaries** — click "📄 Show Summary" to read Claude-generated summary inline; "✨ Summarize" to generate on demand for any paper
- **Client-side filters** — by tag, source, confidence level, date range, and free-text search

### 📚 My List
- Papers you've saved, in reverse chronological order
- **Editable tags** — add/remove inline
- **Reading status** — To Read / Priority Read / Read (date auto-fills when marked Read)
- **Personal notes** — auto-saved textarea per paper
- **On-demand summarization** — generate rich structured summaries for any paper at any time
- **Explore button** — jump to the Explorations tab for any saved paper

### 🔭 Explorations
A 3-pane layout for deep-diving into any paper from your My List:

- **Left pane** — your saved papers list; click to select
- **Middle pane** — the exploration dashboard with two foldable sections:
  - **Literature Survey** — an interactive D3.js force-directed knowledge graph showing relationships between the focal paper and related papers, plus an AI-generated 400–600 word academic literature review
  - **Research Directions** — (coming soon) suggested future research based on the paper
- **Right pane** — auto-scored related papers ranked by semantic relevance (tag overlap, author overlap, title/abstract keyword similarity)

#### Knowledge Graph Details
- **Focal paper** highlighted as a larger purple node
- **Related papers** sized by relevance score
- **Edges** color-coded with AI-generated relation descriptions (5–8 word verb-first phrases like "extends transformer architecture for multimodal tasks")
- **Interactive**: hover for tooltips, drag to reposition nodes, zoom & pan (0.25–4x)
- **Graceful degradation**: falls back to heuristic relation descriptions if the Claude API is unavailable

### ⚙️ Settings
- Edit your research interests live (topics, keywords, authors, venues) with chip-based editors
- Toggle sources (arXiv, Semantic Scholar, HuggingFace, Twitter/X)
- Tune crawl settings (days lookback, max results, confidence threshold, relevance score)
- "🚀 Run Crawl Now" button with live status polling

---

## Architecture

ResearchClaw uses a modular architecture with clean separation of concerns:

```
researchclaw/
├── app/                           # FastAPI application
│   ├── main.py                    # App factory, middleware, routing
│   ├── config.py                  # Path & settings management
│   ├── utils.py                   # Shared helpers
│   ├── models/                    # Pydantic data models
│   │   ├── paper.py               # Paper, PaperListResponse
│   │   ├── literature_survey.py   # PaperNode, RelationEdge, LiteratureSurveyGraph
│   │   ├── explorations.py        # ExplorationMeta, ExplorationInitResponse
│   │   ├── mylist.py              # MyListEntry, MyListUpdate
│   │   └── settings.py            # UserPreferences
│   ├── routes/                    # API endpoint handlers
│   │   ├── papers.py              # Paper listing & on-demand summarization
│   │   ├── mylist.py              # My List CRUD
│   │   ├── explorations.py        # Exploration init, survey generation & status
│   │   ├── settings.py            # Preferences, crawl trigger, status, history
│   │   └── feedback.py            # User feedback (save/dismiss)
│   └── services/                  # Business logic
│       ├── paper_service.py       # Paper parsing & loading from disk
│       ├── summary_service.py     # On-demand Claude summarization
│       ├── mylist_service.py      # My List management & enrichment
│       ├── crawl_service.py       # Background crawl orchestration
│       └── literature_survey_service.py  # Knowledge graph + AI survey generation
├── static/
│   ├── css/                       # Modular stylesheets (base, components, dashboard, mylist, explorations, settings)
│   └── js/                        # Vanilla JS modules
│       ├── state.js               # Global app state
│       ├── utils.js               # HTML escaping, date formatting, markdown conversion
│       ├── api.js                 # All API calls
│       ├── app.js                 # Init & tab switching
│       ├── dashboard.js           # Paper feed, filters, chart
│       ├── mylist.js              # My List rendering & interactions
│       ├── explorations.js        # 3-pane layout, paper selection
│       ├── literature_survey.js   # D3 knowledge graph, survey polling
│       └── settings.js            # Preferences UI
├── templates/
│   └── index.html                 # Single-page app shell
├── app.py                         # Entry point (uvicorn)
├── crawl.py                       # Paper fetching + Claude classification
├── summarize.py                   # Structured summary generation + Telegram notification
├── preferences.yaml               # Your research interests
├── run.sh                         # One-shot: crawl + summarize
├── start_ui.sh                    # Launch the web UI
├── requirements.txt
└── output/
    ├── index.md                   # Paper index (regenerated each crawl)
    ├── papers/                    # One .md per paper (YAML frontmatter + abstract)
    ├── summaries/                 # One .md per generated summary
    └── explorations/              # Per-paper exploration data
        └── {paper_id}/
            ├── meta.json          # Paper metadata
            ├── notes.md           # User notes
            ├── references.json    # References list
            ├── literature_survey.json  # Generated survey + graph data
            └── related_papers/    # Related paper JSONs + index
```

Runtime state files (gitignored): `papers_cache.json`, `feedback.json`, `mylist.json`, `filtered_papers.json`, `crawl_history.json`

---

## Why this is interesting (for developers)

- **Modular service architecture** — Pydantic models, dedicated services, and route handlers keep concerns cleanly separated
- **Multi-source deduplication** — papers from HuggingFace and arXiv often overlap; they're merged and their sources tracked separately
- **Claude as a classifier, not just a summarizer** — instead of keyword matching, Haiku reads each abstract and assigns tags + a semantic confidence score. This dramatically reduces noise.
- **Full paper text fetching** — summaries use the actual arXiv HTML (intro + methodology + conclusion), not just the abstract. Graceful fallback for non-arXiv papers.
- **AI-generated knowledge graphs** — relation descriptions between papers are generated by Claude (with heuristic fallback), visualized as an interactive D3 force-directed graph
- **Literature survey generation** — Claude writes 400–600 word academic reviews with thematic clustering, placing each paper in context
- **Semantic relevance scoring** — related papers ranked by a weighted composite of tag overlap (3x), author overlap (2x), title keywords (1x), and abstract keywords (0.5x)
- **Background task management** — crawls, summarization, and survey generation all run in background threads with status polling
- **Incremental crawling** — `papers_cache.json` tracks what's already been processed so reruns only handle new papers
- **Structured rich summaries** — the summarization prompt extracts Research Questions, Methodology, Loss Functions, Key Equations, and Experimental Findings separately
- **Feedback loop** — marking a paper "Not Relevant" deletes its files immediately; your My List is a persistent annotation layer on top of the crawl
- **Graceful degradation** — knowledge graphs and surveys work without the Claude API by falling back to heuristic descriptions and template-based reviews

---

## Requirements

ResearchClaw is built to run with **[OpenClaw](https://github.com/openclaw/openclaw)** — an open-source personal AI assistant framework that handles scheduling, Telegram notifications, and Claude API integration.

You'll need:
- [OpenClaw](https://docs.openclaw.ai) installed and running
- An Anthropic API key (configured in OpenClaw)
- Python 3.10+
- Optional: Telegram bot token for push notifications

> **Note:** ResearchClaw can also be run standalone (without OpenClaw) by setting environment variables directly in `.env`. OpenClaw is only required for the daily cron scheduling and Telegram notification routing.

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...          # Required: for Claude tagging + summaries
TELEGRAM_BOT_TOKEN=...                 # Optional: for daily Telegram notifications
TELEGRAM_CHAT_ID=...                   # Optional: your Telegram user/chat ID
TWITTER_BEARER_TOKEN=...               # Optional: Twitter/X source (WIP — see below)
```

### Configure your interests

Edit `preferences.yaml`:

```yaml
topics:
  - large language models
  - diffusion models
  - AI safety
  - reasoning

keywords:
  - RLHF
  - fine-tuning
  - transformer
  - chain-of-thought

sources:
  - arxiv
  - semantic_scholar
  - huggingface
  # - twitter   # WIP

days_lookback: 7
max_results_per_source: 20
```

### Run

```bash
# One-shot crawl + summarize
./run.sh

# Launch the web dashboard
./start_ui.sh
# → open http://localhost:7337
```

---

## Sources

| Source | Auth required | Status |
|--------|--------------|--------|
| arXiv | None | ✅ Completed |
| Semantic Scholar | None | ✅ Completed (rate-limited) |
| HuggingFace Daily Papers | None | ✅ Completed |
| Twitter/X | Bearer token | 🚧 WIP — extracts arXiv links from tweets, not yet stable |

> **Twitter/X note:** The Twitter source is functional but considered WIP. The free API tier has tight rate limits and the signal-to-noise ratio depends heavily on who you follow. Contributions to improve this source are welcome.

---

## OpenClaw integration

ResearchClaw is designed to pair with [OpenClaw](https://docs.openclaw.ai) for scheduling and notifications:

```bash
# The daily 8pm cron is set up automatically if you use OpenClaw
# It runs as an isolated agent turn with full API key access

# Manual trigger via OpenClaw
openclaw system event --text "Run ResearchClaw crawl"
```

Without OpenClaw, schedule `./run.sh` via cron manually:
```bash
# Add to crontab: run daily at 8pm
0 20 * * * cd /path/to/researchclaw && ./run.sh >> /tmp/researchclaw.log 2>&1
```

---

## Built with

- [FastAPI](https://fastapi.tiangolo.com/) — web framework
- [Pydantic](https://docs.pydantic.dev/) — data validation & settings management
- [Anthropic Claude](https://www.anthropic.com/) — paper classification, summarization, literature surveys
- [OpenClaw](https://docs.openclaw.ai) — scheduling, notifications, API key management
- [D3.js](https://d3js.org/) — force-directed knowledge graph visualization
- [Chart.js](https://www.chartjs.org/) — dashboard charts
- [arXiv API](https://arxiv.org/help/api/) — paper source
- [Semantic Scholar API](https://api.semanticscholar.org/) — paper source
- [HuggingFace Daily Papers](https://huggingface.co/papers) — curated daily list

---

## Roadmap ideas

- [ ] Full-text fetching for non-arXiv papers (Semantic Scholar + DOI resolvers)
- [ ] Author following — notify when a specific researcher publishes
- [ ] Research Directions — AI-suggested future work based on paper analysis
- [ ] Weekly digest email
- [ ] Export My List to Notion / Obsidian
- [ ] Citation graph — see which papers cite each other
- [ ] Semantic similarity search across your saved papers
- [ ] Twitter/X source improvements (better filtering, verified researcher lists)

---

## Contributing

PRs welcome. If you find this useful and want to extend it — new sources, better prompts, export integrations — open an issue or just send a PR.

If this saved you time, a ⭐ goes a long way.
