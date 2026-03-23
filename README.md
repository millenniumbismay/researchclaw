# 🔬 ResearchCrawl

> **Your personal AI-powered research paper curator.** Set your interests once, get a daily digest of the most relevant papers — tagged, scored, and summarized by Claude.

---

## What it does

ResearchCrawl automatically discovers, filters, and summarizes research papers from multiple sources every day. It's built around one idea: **you should only read papers that actually matter to you**, and you shouldn't have to spend an hour on arXiv to find them.

Every evening at 8pm, it:

1. **Crawls** arXiv, Semantic Scholar, and HuggingFace Daily Papers
2. **Classifies** each paper using Claude Haiku — assigns tags from your interest list and a confidence score (1–5)
3. **Filters** to only papers with confidence ≥ 3
4. **Auto-summarizes** papers with confidence = 5 using structured prompts (Abstract, Introduction Highlights, Research Questions, Methodology & Key Findings)
5. **Notifies** you on Telegram with the top papers of the day
6. **Serves** a local web dashboard where you can browse, save, and annotate everything

---

## The Dashboard

A dark-mode web UI (FastAPI + vanilla JS) with three tabs:

### 📊 Dashboard
- **Stacked bar chart** — papers crawled per day, broken down by confidence level (3/4/5) over the last 90 days
- **Paper feed** — grouped by date, with tag chips, confidence badges, and source labels
- **One-click actions** — "＋ My List" to save, "✕ Not Relevant" to dismiss (and delete the files)
- **Expandable summaries** — click "📄 Show Summary" to read inline; "✨ Summarize" to generate on demand for any paper
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
TWITTER_BEARER_TOKEN=...               # Optional: for Twitter/X source
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
researchcrawl/
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

| Source | Auth required | Notes |
|--------|--------------|-------|
| arXiv | None | Full-text search via arXiv API |
| Semantic Scholar | None | Free public API (rate-limited) |
| HuggingFace Daily Papers | None | Scraped from huggingface.co/papers |
| Twitter/X | Bearer token | Searches for arxiv links in tweets |

---

## Roadmap ideas

- [ ] Full-text fetching (PDF → text) for better classification and summaries
- [ ] Author following — notify when a specific researcher publishes
- [ ] Weekly digest email
- [ ] Export My List to Notion / Obsidian
- [ ] Citation graph — see which papers cite each other
- [ ] Semantic similarity search across your saved papers

---

## Built with

- [FastAPI](https://fastapi.tiangolo.com/) — web framework
- [Anthropic Claude](https://www.anthropic.com/) — paper classification + summarization
- [Chart.js](https://www.chartjs.org/) — dashboard charts
- [arXiv API](https://arxiv.org/help/api/) — paper source
- [Semantic Scholar API](https://api.semanticscholar.org/) — paper source
- [HuggingFace Daily Papers](https://huggingface.co/papers) — curated daily list

---

## Contributing

PRs welcome. If you find this useful and want to extend it — new sources, better prompts, export integrations — open an issue or just send a PR.

If this saved you time, a ⭐ goes a long way.
