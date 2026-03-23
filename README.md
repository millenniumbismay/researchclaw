# 🦞 ResearchClaw

> **Your personal AI-powered research paper curator.** Set your interests once, get a daily digest of the most relevant papers — tagged, scored, and summarized by Claude.

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

## What it does

ResearchClaw automatically discovers, filters, and summarizes research papers from multiple sources every day. It's built around one idea: **you should only read papers that actually matter to you**, and you shouldn't have to spend an hour on arXiv to find them.

Every evening at 8pm, it:

1. **Crawls** arXiv, Semantic Scholar, and HuggingFace Daily Papers
2. **Classifies** each paper using Claude Haiku — assigns tags from your interest list and a confidence score (1–5)
3. **Filters** to only papers with confidence ≥ 3
4. **Fetches full paper text** from arXiv HTML for rich, accurate summaries
5. **Auto-summarizes** papers with confidence = 5 using structured prompts (Abstract, Introduction Highlights, Research Questions, Methodology & Key Findings)
6. **Notifies** you on Telegram with the top papers of the day
7. **Serves** a local web dashboard where you can browse, save, and annotate everything

---

## The Dashboard

A dark-mode web UI (FastAPI + vanilla JS) with three tabs:

### 📊 Dashboard
- **Stacked bar chart** — papers crawled per day, broken down by confidence level (3/4/5) over the last 90 days
- **Paper feed** — grouped by date, with tag chips, confidence badges, and source labels
- **One-click actions** — "＋ My List" to save, "✕ Not Relevant" to dismiss (and delete the files)
- **Expandable abstract** — click "▼ Abstract" on any card to read the full abstract inline
- **Expandable summaries** — click "📄 Show Summary" to read Claude-generated summary inline; "✨ Summarize" to generate on demand for any paper
- **Client-side filters** — by tag, source, confidence level, date range, and free-text search

### 📚 My List
- Papers you've saved, in reverse chronological order
- **Editable tags** — add/remove inline
- **Reading status** — To Read / Priority Read / Read (date auto-fills when marked Read)
- **Personal notes** — auto-saved textarea per paper
- **On-demand summarization** — generate rich structured summaries for any paper at any time

### ⚙️ Settings
- Edit your research interests live (topics, keywords, authors, venues)
- Toggle sources (arXiv, Semantic Scholar, HuggingFace, Twitter/X)
- Tune crawl settings (days lookback, max results, confidence threshold)
- "🚀 Run Crawl Now" button with live status polling

---

## Why this is interesting (for developers)

- **Multi-source deduplication** — papers from HuggingFace and arXiv often overlap; they're merged and their sources tracked separately
- **Claude as a classifier, not just a summarizer** — instead of keyword matching, Haiku reads each abstract and assigns tags + a semantic confidence score. This dramatically reduces noise.
- **Full paper text fetching** — summaries use the actual arXiv HTML (intro + methodology + conclusion), not just the abstract. Graceful fallback for non-arXiv papers.
- **Incremental crawling** — `papers_cache.json` tracks what's already been processed so reruns only handle new papers
- **Structured rich summaries** — the summarization prompt extracts Research Questions, Methodology, Loss Functions, Key Equations, and Experimental Findings separately — not just a paragraph summary
- **Feedback loop** — marking a paper "Not Relevant" deletes its files immediately; your My List is a persistent annotation layer on top of the crawl
- **Separation of concerns** — `crawl.py` fetches + classifies, `summarize.py` generates summaries + notifies, `ui.py` serves everything. Easy to extend or swap components.

---

## Setup

### Requirements

```bash
python3 -m venv .venv
source .venv/bin/activate   # or .venv/bin/activate.fish
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

## File structure

```
researchclaw/
├── crawl.py              # Fetches papers, runs Claude classification
├── summarize.py          # Generates structured summaries, sends Telegram notification
├── ui.py                 # FastAPI web dashboard (Dashboard + My List + Settings)
├── preferences.yaml      # Your research interests — edit anytime
├── run.sh                # One-shot: crawl + summarize
├── start_ui.sh           # Launch the web UI
├── requirements.txt
└── output/
    ├── index.md          # Regenerated after each run
    ├── papers/           # One .md per paper (frontmatter + abstract)
    └── summaries/        # One .md per generated summary (plain markdown)
```

Runtime state files (gitignored): `papers_cache.json`, `feedback.json`, `mylist.json`, `filtered_papers.json`

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

## Roadmap ideas

- [ ] Full-text fetching for non-arXiv papers (Semantic Scholar + DOI resolvers)
- [ ] Author following — notify when a specific researcher publishes
- [ ] Weekly digest email
- [ ] Export My List to Notion / Obsidian
- [ ] Citation graph — see which papers cite each other
- [ ] Semantic similarity search across your saved papers
- [ ] Twitter/X source improvements (better filtering, verified researcher lists)

---

## Built with

- [FastAPI](https://fastapi.tiangolo.com/) — web framework
- [Anthropic Claude](https://www.anthropic.com/) — paper classification + summarization
- [OpenClaw](https://docs.openclaw.ai) — scheduling, notifications, API key management
- [Chart.js](https://www.chartjs.org/) — dashboard charts
- [arXiv API](https://arxiv.org/help/api/) — paper source
- [Semantic Scholar API](https://api.semanticscholar.org/) — paper source
- [HuggingFace Daily Papers](https://huggingface.co/papers) — curated daily list

---

## Contributing

PRs welcome. If you find this useful and want to extend it — new sources, better prompts, export integrations — open an issue or just send a PR.

If this saved you time, a ⭐ goes a long way.
