"""ResearchCrawl UI — FastAPI app with Dashboard, My List, and Settings tabs."""

import json
import re
import subprocess
import threading
import datetime
from pathlib import Path

import yaml
import markdown as md_lib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

# ---------------------------------------------------------------------------
# App + CORS
# ---------------------------------------------------------------------------
app = FastAPI(title="ResearchCrawl UI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
PREFS_PATH = BASE_DIR / "preferences.yaml"
OUTPUT_DIR = BASE_DIR / "output"
PAPERS_DIR = OUTPUT_DIR / "papers"
SUMMARIES_DIR = OUTPUT_DIR / "summaries"
FEEDBACK_PATH = BASE_DIR / "feedback.json"
MYLIST_PATH = BASE_DIR / "mylist.json"
CRAWL_HISTORY_PATH = BASE_DIR / "crawl_history.json"

# Ensure summaries directory exists on startup
SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(title: str) -> str:
    name = title.lower()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name.strip())
    name = re.sub(r"-+", "-", name)
    return name[:80].rstrip("-")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def parse_paper(path: Path) -> dict:
    text = path.read_text()
    parts = text.split("---\n", 2)
    if len(parts) >= 3:
        try:
            fm = yaml.safe_load(parts[1]) or {}
        except Exception:
            fm = {}
        body = parts[2].strip()
    else:
        fm, body = {}, text

    url = str(fm.get("url", ""))
    m = re.search(r"arxiv\.org/abs/([^\s/]+)", url)
    if m:
        pid = "arxiv:" + m.group(1)
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", str(fm.get("title", path.stem)).lower()).strip("-")
        pid = slug[:80]

    authors_raw = fm.get("authors", "")
    if isinstance(authors_raw, list):
        authors = [str(a).strip() for a in authors_raw if str(a).strip()]
    else:
        authors = [a.strip() for a in str(authors_raw).split(",") if a.strip()]

    tags = fm.get("tags") or []
    if not isinstance(tags, list):
        tags = []

    def _int(v, d=0):
        try:
            return int(v or d)
        except Exception:
            return d

    def _float(v, d=0.0):
        try:
            return float(v or d)
        except Exception:
            return d

    summary_path = SUMMARIES_DIR / f"{path.stem}.md"
    if summary_path.exists():
        try:
            summary = summary_path.read_text(encoding="utf-8").strip()
            has_summary = bool(summary)
        except Exception:
            summary = ""
            has_summary = False
    else:
        summary = ""
        has_summary = False

    return {
        "id": pid,
        "title": str(fm.get("title", path.stem)),
        "authors": [str(a) for a in authors],
        "date": str(fm.get("date", "")),
        "url": url,
        "source": str(fm.get("source", "")),
        "source_tags": list(fm.get("source_tags") or []),
        "tags": tags,
        "confidence": _int(fm.get("confidence")),
        "relevance_score": _float(fm.get("relevance_score")),
        "abstract": str(fm.get("abstract", "") or ""),
        "affiliation": "",
        "summary": summary,
        "has_summary": has_summary,
    }


def _update_crawl_history(count: int):
    history = load_json(CRAWL_HISTORY_PATH, [])
    today = datetime.date.today().isoformat()
    for e in history:
        if e.get("date") == today:
            e["count"] = count
            save_json(CRAWL_HISTORY_PATH, history)
            return
    history.append({"date": today, "count": count})
    save_json(CRAWL_HISTORY_PATH, history)


# ---------------------------------------------------------------------------
# Subprocess state
# ---------------------------------------------------------------------------
_crawl_proc: subprocess.Popen | None = None
_last_run: str | None = None
_last_paper_count: int = 0
_state_lock = threading.Lock()


def _paper_count() -> int:
    return len(list(PAPERS_DIR.glob("*.md"))) if PAPERS_DIR.exists() else 0


def _run_crawl_bg():
    global _crawl_proc, _last_run, _last_paper_count
    try:
        for script in ("crawl.py", "summarize.py"):
            proc = subprocess.Popen(
                [".venv/bin/python", script],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            with _state_lock:
                _crawl_proc = proc
            proc.wait()
    finally:
        with _state_lock:
            _crawl_proc = None
            _last_run = datetime.datetime.now(datetime.timezone.utc).isoformat()
            _last_paper_count = _paper_count()
        _update_crawl_history(_last_paper_count)


# ---------------------------------------------------------------------------
# HTML — full SPA
# ---------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>ResearchCrawl</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #0f1117;
  --card: #1a1d27;
  --accent: #7c6af7;
  --accent-dim: #5a50c4;
  --text: #e4e6f0;
  --muted: #6b7080;
  --border: #2a2d3e;
  --danger: #f76a6a;
  --success: #6af7a0;
  --warn: #f7b76a;
  --radius: 8px;
  --chip-radius: 20px;
  --font: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
body { background: var(--bg); color: var(--text); font-family: var(--font); min-height: 100vh; padding-bottom: 72px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* header */
header {
  display: flex; align-items: stretch; gap: 0;
  padding: 0 0 0 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
  position: sticky; top: 0; z-index: 50;
}
header h1 { font-size: 1.1rem; font-weight: 700; letter-spacing: -0.02em; padding: 18px 24px 18px 0; white-space: nowrap; align-self: center; }

/* tabs */
.tab-nav { display: flex; gap: 0; flex: 1; }
.tab-btn {
  padding: 0 18px; height: 58px;
  font-size: 0.88rem; font-weight: 500;
  color: var(--muted); background: none; border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer; transition: color 0.15s, border-color 0.15s; white-space: nowrap;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-pane { display: none; }
.tab-pane.active { display: block; }

/* main */
.main-content { max-width: 900px; margin: 0 auto; padding: 24px 22px; display: flex; flex-direction: column; gap: 16px; }

/* card */
.card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 22px; }
.card h2 { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 14px; }

/* chart */
.chart-wrap { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px 22px 14px; }
.chart-title { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 12px; }

/* filter bar */
.filter-bar {
  background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 12px 16px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
}
.filter-input {
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); font-size: 0.85rem; padding: 6px 11px; outline: none;
  min-width: 180px; flex: 1; transition: border-color 0.15s;
}
.filter-input:focus { border-color: var(--accent); }
.filter-input::placeholder { color: var(--muted); }
.filter-sep { width: 1px; background: var(--border); height: 20px; flex-shrink: 0; }
.filter-label { font-size: 0.78rem; color: var(--muted); white-space: nowrap; }
.filter-range { accent-color: var(--accent); cursor: pointer; width: 72px; }
.filter-date {
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); font-size: 0.8rem; padding: 5px 8px; outline: none; colorscheme: dark;
}
.filter-date:focus { border-color: var(--accent); }
.filter-src-lbl { display: inline-flex; align-items: center; gap: 5px; font-size: 0.8rem; color: var(--muted); cursor: pointer; }
.filter-src-lbl input[type=checkbox] { accent-color: var(--accent); cursor: pointer; }

/* tag filter dropdown */
.tag-filter-wrap { position: relative; }
.tag-filter-btn {
  background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
  color: var(--text); font-size: 0.8rem; padding: 5px 11px; cursor: pointer; white-space: nowrap;
}
.tag-filter-btn:hover { border-color: var(--accent); }
.tag-filter-menu {
  display: none; position: absolute; top: calc(100% + 4px); left: 0;
  background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 6px; min-width: 150px; max-height: 200px; overflow-y: auto;
  z-index: 200; box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}
.tag-filter-menu.open { display: block; }
.tag-opt { display: flex; align-items: center; gap: 7px; padding: 5px 6px; font-size: 0.8rem; cursor: pointer; border-radius: 4px; }
.tag-opt:hover { background: rgba(255,255,255,0.05); }
.tag-opt input { accent-color: var(--accent); cursor: pointer; }

/* date group header */
.date-header { font-size: 0.76rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); padding: 6px 0 4px; margin-top: 6px; }

/* paper card */
.paper-card {
  background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden; transition: border-color 0.15s, opacity 0.2s; margin-bottom: 10px;
}
.paper-card:hover { border-color: rgba(124,106,247,0.4); }
.paper-card.dimmed { opacity: 0.38; }
.paper-card-body { padding: 14px 16px 10px; cursor: pointer; user-select: none; }
.paper-title { font-size: 0.93rem; font-weight: 600; line-height: 1.4; margin-bottom: 5px; display: flex; justify-content: space-between; gap: 8px; }
.paper-title a { color: var(--text); pointer-events: all; }
.paper-title a:hover { color: var(--accent); text-decoration: none; }
.expand-hint { font-size: 0.7rem; color: var(--muted); flex-shrink: 0; align-self: flex-start; padding-top: 3px; }
.paper-meta { font-size: 0.79rem; color: var(--muted); margin-bottom: 7px; display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.paper-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.tag-chip { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: var(--chip-radius); font-size: 0.72rem; font-weight: 500; border: 1px solid; }
.badge { display: inline-flex; align-items: center; padding: 2px 7px; border-radius: 4px; font-size: 0.71rem; font-weight: 600; }
.badge-arxiv { background: rgba(124,106,247,0.14); color: #a99bf9; }
.badge-hf { background: rgba(247,183,106,0.14); color: #f7b76a; }
.badge-ss { background: rgba(106,212,247,0.14); color: #6ad4f7; }
.badge-src { background: rgba(107,112,128,0.14); color: var(--muted); }
.badge-c0 { background: rgba(107,112,128,0.14); color: var(--muted); }
.badge-c1, .badge-c2 { background: rgba(107,112,128,0.14); color: var(--muted); }
.badge-c3 { background: rgba(247,224,106,0.14); color: #f7e06a; }
.badge-c4 { background: rgba(247,183,106,0.14); color: var(--warn); }
.badge-c5 { background: rgba(106,247,160,0.14); color: var(--success); }

/* paper actions */
.paper-actions { display: flex; gap: 6px; padding: 0 16px 12px; flex-wrap: wrap; }
.btn-action { padding: 4px 12px; border-radius: 5px; font-size: 0.78rem; font-weight: 600; cursor: pointer; border: 1px solid; transition: background 0.15s; line-height: 1.5; }
.btn-mylist { background: rgba(124,106,247,0.1); color: var(--accent); border-color: rgba(124,106,247,0.3); }
.btn-mylist:hover:not(:disabled) { background: rgba(124,106,247,0.2); }
.btn-mylist.in-list { background: rgba(106,247,160,0.08); color: var(--success); border-color: rgba(106,247,160,0.25); cursor: default; }
.btn-notrel { background: rgba(247,106,106,0.08); color: var(--danger); border-color: rgba(247,106,106,0.25); }
.btn-notrel:hover { background: rgba(247,106,106,0.16); }
.btn-undo { background: rgba(107,112,128,0.1); color: var(--muted); border-color: rgba(107,112,128,0.25); }
.btn-undo:hover { background: rgba(107,112,128,0.2); color: var(--text); }

/* summary */
.paper-summary { display: none; padding: 11px 16px 13px; font-size: 0.84rem; line-height: 1.68; color: #adb0cc; border-top: 1px solid var(--border); word-break: break-word; }
.paper-summary.open { display: block; }
.paper-summary h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 8px 0 3px; }
.paper-summary p { margin-bottom: 5px; }
.paper-summary a { color: var(--accent); }
.paper-summary em { color: var(--muted); font-size: 0.78rem; }

/* dashboard inline summary panel */
.dash-summary-panel { display: none; margin: 0 16px 12px; padding: 12px; background: rgba(255,255,255,0.025); border-left: 3px solid var(--accent); border-radius: 0 4px 4px 0; font-size: 0.84rem; line-height: 1.68; color: #adb0cc; word-break: break-word; }
.dash-summary-panel.open { display: block; }
.dash-summary-panel h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 8px 0 3px; }
.dash-summary-panel p { margin-bottom: 5px; }
.dash-summary-panel a { color: var(--accent); }

/* summary action buttons */
.btn-show-summary { background: rgba(124,106,247,0.08); color: var(--accent); border-color: rgba(124,106,247,0.25); }
.btn-show-summary:hover { background: rgba(124,106,247,0.18); }
.no-summary-label { font-size: 0.78rem; color: var(--muted); opacity: 0.55; padding: 4px 10px; }

/* my list */
.mylist-card {
  background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 16px 18px; position: relative; transition: opacity 0.35s; margin-bottom: 12px;
}
.mylist-card.removing { opacity: 0; }
.mylist-title { font-size: 0.93rem; font-weight: 600; margin-bottom: 3px; padding-right: 80px; }
.mylist-title a { color: var(--text); }
.mylist-title a:hover { color: var(--accent); text-decoration: none; }
.mylist-authors { font-size: 0.79rem; color: var(--muted); margin-bottom: 10px; }
.mylist-tags-row { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; margin-bottom: 10px; }
.ml-tag { display: inline-flex; align-items: center; gap: 3px; padding: 2px 8px; border-radius: var(--chip-radius); font-size: 0.74rem; font-weight: 500; background: rgba(124,106,247,0.1); color: var(--accent); border: 1px solid rgba(124,106,247,0.28); }
.ml-tag-x { cursor: pointer; opacity: 0.6; font-size: 0.82rem; line-height: 1; }
.ml-tag-x:hover { opacity: 1; color: var(--danger); }
.ml-tag-inp { background: var(--bg); border: 1px solid var(--border); border-radius: 4px; color: var(--text); font-size: 0.76rem; padding: 2px 7px; width: 85px; outline: none; }
.ml-tag-inp:focus { border-color: var(--accent); }
.mylist-controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; margin-bottom: 10px; }
.ml-field { display: flex; flex-direction: column; gap: 3px; }
.ml-field-lbl { font-size: 0.74rem; color: var(--muted); font-weight: 500; }
.ml-select, .ml-date { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 0.83rem; padding: 5px 9px; outline: none; colorscheme: dark; }
.ml-select:focus, .ml-date:focus { border-color: var(--accent); }
.ml-notes { width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 0.83rem; padding: 7px 10px; resize: vertical; min-height: 52px; outline: none; font-family: var(--font); }
.ml-notes:focus { border-color: var(--accent); }
.btn-rm { position: absolute; top: 12px; right: 12px; background: none; border: 1px solid var(--border); border-radius: 5px; color: var(--muted); font-size: 0.77rem; padding: 3px 8px; cursor: pointer; transition: background 0.15s, color 0.15s, border-color 0.15s; }
.btn-rm:hover { background: rgba(247,106,106,0.1); color: var(--danger); border-color: rgba(247,106,106,0.3); }

/* summarize button */
.btn-summarize { background: rgba(34,197,94,0.1); color: #22c55e; border-color: rgba(34,197,94,0.3); }
.btn-summarize:hover:not(:disabled) { background: rgba(34,197,94,0.2); }
.btn-summarize:disabled { opacity: 0.6; cursor: wait; }
.btn-viewsummary { background: rgba(107,112,128,0.1); color: var(--muted); border-color: rgba(107,112,128,0.25); }
.btn-viewsummary:hover { background: rgba(107,112,128,0.2); color: var(--text); }
.ml-summary-area { margin-top: 10px; font-size: 0.84rem; line-height: 1.68; color: #adb0cc; word-break: break-word; border-top: 1px solid var(--border); padding-top: 10px; }
.ml-summary-area p { margin-bottom: 5px; }
.ml-summary-area h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 8px 0 3px; }

/* empty state */
.empty-state { text-align: center; padding: 56px 20px; color: var(--muted); font-size: 0.88rem; line-height: 1.6; }
.empty-state h3 { font-size: 0.98rem; margin-bottom: 7px; color: var(--text); font-weight: 600; }

/* chip editor */
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; min-height: 36px; }
.chip { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; background: rgba(124,106,247,0.18); color: var(--accent); border: 1px solid rgba(124,106,247,0.35); border-radius: var(--chip-radius); font-size: 0.84rem; font-weight: 500; }
.chip.muted { background: rgba(107,112,128,0.12); color: var(--muted); border-color: rgba(107,112,128,0.25); }
.chip-x { cursor: pointer; font-size: 1rem; line-height: 1; opacity: 0.7; }
.chip-x:hover { opacity: 1; color: var(--danger); }
.empty-label { color: var(--muted); font-size: 0.84rem; font-style: italic; align-self: center; }
.chip-input-row { display: flex; gap: 8px; }
.chip-input-row input { flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 0.88rem; padding: 7px 12px; outline: none; transition: border-color 0.15s; }
.chip-input-row input:focus { border-color: var(--accent); }
.chip-input-row input::placeholder { color: var(--muted); }
.btn-small { background: var(--accent); color: #fff; border: none; border-radius: 6px; padding: 7px 16px; font-size: 0.86rem; font-weight: 600; cursor: pointer; white-space: nowrap; transition: background 0.15s; }
.btn-small:hover { background: var(--accent-dim); }

/* sources */
.sources-grid { display: flex; flex-wrap: wrap; gap: 14px; }
.source-item { display: flex; align-items: center; gap: 8px; font-size: 0.9rem; cursor: pointer; }
.source-item input[type=checkbox] { width: 17px; height: 17px; accent-color: var(--accent); cursor: pointer; }

/* settings */
.settings-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 18px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 0.82rem; color: var(--muted); font-weight: 500; }
.field input[type=number], .field input[type=text] { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 0.9rem; padding: 8px 12px; outline: none; transition: border-color 0.15s; }
.field input:focus { border-color: var(--accent); }
.field input::placeholder { color: var(--muted); }
.slider-row { display: flex; align-items: center; gap: 10px; }
.slider-row input[type=range] { flex: 1; accent-color: var(--accent); cursor: pointer; }
.slider-val { font-size: 0.88rem; color: var(--accent); font-weight: 600; min-width: 36px; text-align: right; }
.full-width { grid-column: 1 / -1; }

/* action bar */
.action-bar { position: fixed; bottom: 0; left: 0; right: 0; background: rgba(26,29,39,0.96); backdrop-filter: blur(12px); border-top: 1px solid var(--border); display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding: 12px 28px; z-index: 100; }
.btn { display: inline-flex; align-items: center; gap: 7px; border: none; border-radius: 8px; padding: 9px 20px; font-size: 0.88rem; font-weight: 600; cursor: pointer; transition: background 0.15s, opacity 0.15s; }
.btn:disabled { opacity: 0.45; cursor: not-allowed; }
.btn-save { background: var(--card); color: var(--text); border: 1px solid var(--border); }
.btn-save:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.btn-run { background: var(--accent); color: #fff; }
.btn-run:hover:not(:disabled) { background: var(--accent-dim); }
.status-msg { font-size: 0.82rem; color: var(--muted); margin-right: 6px; }
.spinner { width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.25); border-top-color: #fff; border-radius: 50%; animation: spin 0.7s linear infinite; display: none; }
@keyframes spin { to { transform: rotate(360deg); } }

/* toast */
#toast { position: fixed; bottom: 70px; right: 20px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 9px 16px; font-size: 0.85rem; color: var(--text); opacity: 0; pointer-events: none; transition: opacity 0.22s; z-index: 300; }
#toast.show { opacity: 1; }

@media (max-width: 600px) {
  header { padding: 0 0 0 14px; }
  .main-content { padding: 14px 10px; }
  .action-bar { padding: 10px 14px; }
  .tab-btn { padding: 0 10px; font-size: 0.8rem; }
}
</style>
</head>
<body>

<header>
  <h1>🔬 ResearchCrawl</h1>
  <nav class="tab-nav">
    <button class="tab-btn active" data-tab="dashboard" onclick="switchTab('dashboard')">📊 Dashboard</button>
    <button class="tab-btn" data-tab="mylist" onclick="switchTab('mylist')">📚 My List</button>
    <button class="tab-btn" data-tab="settings" onclick="switchTab('settings')">⚙️ Settings</button>
  </nav>
</header>

<!-- DASHBOARD -->
<div id="tab-dashboard" class="tab-pane active">
  <div class="main-content">
    <div class="chart-wrap">
      <div class="chart-title">Papers Crawled (Last 90 Days)</div>
      <canvas id="crawl-chart" height="70"></canvas>
    </div>
    <div class="filter-bar">
      <input class="filter-input" id="filter-search" type="text" placeholder="Search title, authors…" oninput="applyFilters()"/>
      <div class="filter-sep"></div>
      <div id="fsrc" style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;"></div>
      <div class="filter-sep"></div>
      <div class="tag-filter-wrap">
        <button class="tag-filter-btn" id="tag-filter-btn" onclick="toggleTagMenu()">Tags ▾</button>
        <div class="tag-filter-menu" id="tag-filter-menu"></div>
      </div>
      <div class="filter-sep"></div>
      <span class="filter-label">Min conf:</span>
      <input class="filter-range" id="filter-conf" type="range" min="0" max="5" step="1" value="0" oninput="document.getElementById('conf-val').textContent=this.value;applyFilters()"/>
      <span id="conf-val" style="font-size:0.8rem;color:var(--accent);font-weight:600;min-width:12px;">0</span>
      <div class="filter-sep"></div>
      <span class="filter-label">From:</span>
      <input class="filter-date" id="filter-from" type="date" onchange="applyFilters()"/>
      <span class="filter-label">To:</span>
      <input class="filter-date" id="filter-to" type="date" onchange="applyFilters()"/>
    </div>
    <div id="paper-feed"><div class="empty-state"><p>Loading papers…</p></div></div>
  </div>
</div>

<!-- MY LIST -->
<div id="tab-mylist" class="tab-pane">
  <div class="main-content">
    <div id="mylist-feed">
      <div class="empty-state">
        <h3>No papers yet.</h3>
        <p>Go to Dashboard and click ＋ My List on papers you find interesting.</p>
      </div>
    </div>
  </div>
</div>

<!-- SETTINGS -->
<div id="tab-settings" class="tab-pane">
  <div class="main-content">
    <div class="card">
      <h2>Topics</h2>
      <div class="chip-row" id="chips-topics"></div>
      <div class="chip-input-row">
        <input id="input-topics" type="text" placeholder="Add topic…"/>
        <button class="btn-small" onclick="addChip('topics')">Add</button>
      </div>
    </div>
    <div class="card">
      <h2>Keywords</h2>
      <div class="chip-row" id="chips-keywords"></div>
      <div class="chip-input-row">
        <input id="input-keywords" type="text" placeholder="Add keyword…"/>
        <button class="btn-small" onclick="addChip('keywords')">Add</button>
      </div>
    </div>
    <div class="card">
      <h2>Authors</h2>
      <div class="chip-row" id="chips-authors"></div>
      <div class="chip-input-row">
        <input id="input-authors" type="text" placeholder="Add author…"/>
        <button class="btn-small" onclick="addChip('authors')">Add</button>
      </div>
    </div>
    <div class="card">
      <h2>Venues</h2>
      <div class="chip-row" id="chips-venues"></div>
      <div class="chip-input-row">
        <input id="input-venues" type="text" placeholder="Add venue…"/>
        <button class="btn-small" onclick="addChip('venues')">Add</button>
      </div>
    </div>
    <div class="card">
      <h2>Sources</h2>
      <div class="sources-grid" id="sources-grid"></div>
    </div>
    <div class="card">
      <h2>Settings</h2>
      <div class="settings-grid">
        <div class="field">
          <label for="days_lookback">Days lookback</label>
          <input type="number" id="days_lookback" min="1" max="365" step="1"/>
        </div>
        <div class="field">
          <label for="max_results_per_source">Max results per source</label>
          <input type="number" id="max_results_per_source" min="1" max="500" step="1"/>
        </div>
        <div class="field">
          <label>Min relevance score (<span id="score-display">0.6</span>)</label>
          <div class="slider-row">
            <input type="range" id="min_relevance_score" min="0" max="1" step="0.05"
                   oninput="document.getElementById('score-display').textContent=(+this.value).toFixed(2);document.getElementById('slider-val-display').textContent=(+this.value).toFixed(2)"/>
            <span class="slider-val" id="slider-val-display">0.60</span>
          </div>
        </div>
        <div class="field full-width">
          <label for="twitter_search_query">Twitter search query</label>
          <input type="text" id="twitter_search_query" placeholder="Auto-generated from topics/keywords"/>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ACTION BAR -->
<div class="action-bar">
  <span class="status-msg" id="status-msg"></span>
  <button class="btn btn-save" onclick="savePrefs()">💾 Save Preferences</button>
  <button class="btn btn-run" id="btn-run" onclick="runCrawl()">
    <span class="spinner" id="run-spinner"></span>
    <span id="run-label">🚀 Run Crawl Now</span>
  </button>
</div>

<div id="toast"></div>

<script>
// ============================================================
// STATE
// ============================================================
const SOURCES_ALL = ['arxiv','semantic_scholar','huggingface','twitter'];
const TAG_PALETTE = [
  {bg:'rgba(124,106,247,0.15)',color:'#a99bf9',border:'rgba(124,106,247,0.38)'},
  {bg:'rgba(247,106,106,0.15)',color:'#f78f8f',border:'rgba(247,106,106,0.38)'},
  {bg:'rgba(247,183,106,0.15)',color:'#f7b76a',border:'rgba(247,183,106,0.38)'},
  {bg:'rgba(106,247,160,0.15)',color:'#6af7a0',border:'rgba(106,247,160,0.38)'},
  {bg:'rgba(106,212,247,0.15)',color:'#6ad4f7',border:'rgba(106,212,247,0.38)'},
  {bg:'rgba(247,106,240,0.15)',color:'#f76af0',border:'rgba(247,106,240,0.38)'},
  {bg:'rgba(247,224,106,0.15)',color:'#f7e06a',border:'rgba(247,224,106,0.38)'},
];
const chipData = {topics:[],keywords:[],authors:[],venues:[]};
let allPapers = [];
let myListState = {};
let crawlHistory = [];
let crawlChart = null;
let pollTimer = null;
let activeTagFilters = new Set();
let activeSourceFilters = new Set();
let expandedCards = new Set();

// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
  buildSourcesUI();
  ['topics','keywords','authors','venues'].forEach(k => {
    document.getElementById('input-' + k).addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); addChip(k); }
    });
  });
  document.addEventListener('click', e => {
    if (!e.target.closest('.tag-filter-wrap'))
      document.getElementById('tag-filter-menu').classList.remove('open');
  });
  await Promise.all([loadPapers(), loadMyList(), loadCrawlHistory(), loadPrefs()]);
  renderPaperFeed();
  renderMyList();
  initChart();
  checkStatus();
});

// ============================================================
// TABS
// ============================================================
function switchTab(name) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelector('[data-tab="' + name + '"]').classList.add('active');
}

// ============================================================
// DATA LOADING
// ============================================================
async function loadPapers() {
  try {
    const r = await fetch('/api/papers');
    allPapers = await r.json();
    buildFilterOptions();
  } catch(e) { allPapers = []; }
}

async function loadMyList() {
  try {
    const r = await fetch('/api/mylist');
    const data = await r.json();
    myListState = {};
    data.forEach(e => { myListState[e.paper_id] = e; });
  } catch(e) { myListState = {}; }
}

async function loadCrawlHistory() {
  try {
    const r = await fetch('/api/crawl-history');
    crawlHistory = await r.json();
  } catch(e) { crawlHistory = []; }
}

// ============================================================
// FILTER OPTIONS
// ============================================================
function buildFilterOptions() {
  const allTags = new Set();
  const allSources = new Set();
  allPapers.forEach(p => {
    (p.tags || []).forEach(t => allTags.add(t));
    if (p.source) allSources.add(p.source);
  });
  activeSourceFilters = new Set(allSources);

  const sw = document.getElementById('fsrc');
  sw.innerHTML = [...allSources].sort().map(s =>
    `<label class="filter-src-lbl">
       <input type="checkbox" checked value="${esc(s)}" onchange="toggleSrcFilter('${esc(s)}',this.checked)"/>
       ${esc(s)}
     </label>`
  ).join('');

  const menu = document.getElementById('tag-filter-menu');
  menu.innerHTML = allTags.size === 0
    ? '<div style="padding:7px 8px;font-size:0.78rem;color:var(--muted)">No tags yet</div>'
    : [...allTags].sort().map(t =>
        `<label class="tag-opt">
           <input type="checkbox" value="${esc(t)}" onchange="toggleTagFilter('${escA(t)}',this.checked)"/>
           ${esc(t)}
         </label>`
      ).join('');
  updateTagBtn();
}

function toggleTagMenu() {
  document.getElementById('tag-filter-menu').classList.toggle('open');
}
function toggleTagFilter(tag, on) {
  on ? activeTagFilters.add(tag) : activeTagFilters.delete(tag);
  updateTagBtn(); applyFilters();
}
function updateTagBtn() {
  const n = activeTagFilters.size;
  document.getElementById('tag-filter-btn').textContent = n ? `Tags (${n}) ▾` : 'Tags ▾';
}
function toggleSrcFilter(src, on) {
  on ? activeSourceFilters.add(src) : activeSourceFilters.delete(src);
  applyFilters();
}

// ============================================================
// PAPER FEED
// ============================================================
function getFiltered() {
  const q = document.getElementById('filter-search').value.trim().toLowerCase();
  const minC = +document.getElementById('filter-conf').value;
  const from = document.getElementById('filter-from').value;
  const to   = document.getElementById('filter-to').value;
  return allPapers.filter(p => {
    if (activeSourceFilters.size && !activeSourceFilters.has(p.source)) return false;
    if (activeTagFilters.size) {
      const pt = new Set(p.tags || []);
      if (![...activeTagFilters].some(t => pt.has(t))) return false;
    }
    if (p.confidence < minC) return false;
    if (from && p.date < from) return false;
    if (to   && p.date > to)   return false;
    if (q) {
      const hay = ((p.title||'') + ' ' + (p.authors||[]).join(' ')).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function applyFilters() { renderPaperFeed(); }

function renderPaperFeed() {
  const feed = document.getElementById('paper-feed');
  const papers = getFiltered();
  if (!papers.length) {
    feed.innerHTML = '<div class="empty-state"><h3>No papers found.</h3><p>Try adjusting filters or run the crawl.</p></div>';
    return;
  }
  const byDate = {};
  papers.forEach(p => { const d = p.date||'Unknown'; (byDate[d]||(byDate[d]=[])).push(p); });
  const dates = Object.keys(byDate).sort((a,b) => b.localeCompare(a));
  feed.innerHTML = dates.map(d =>
    `<div class="date-header">${fmtDate(d)}</div>` + byDate[d].map(paperCardHtml).join('')
  ).join('');
}

function paperCardHtml(p) {
  const fb = p.feedback ? p.feedback.action : null;
  const inML = !!myListState[p.id];
  const notRel = fb === 'not_relevant';
  const authors = p.authors || [];
  const authStr = authors.length <= 3 ? authors.join(', ') : authors.slice(0,3).join(', ') + ' et al.';
  const tagChips = (p.tags||[]).map(t => {
    const s = tagSty(t);
    return `<span class="tag-chip" style="background:${s.bg};color:${s.color};border-color:${s.border}">${esc(t)}</span>`;
  }).join('');
  const expanded = expandedCards.has(p.id);
  const cid = cId(p.id);

  let actBtns = '';
  if (fb === 'mylist' || inML) {
    actBtns = `<button class="btn-action btn-mylist in-list" disabled>✓ In My List</button>`;
  } else if (notRel) {
    actBtns = `<button class="btn-action btn-undo" onclick="doFeedback('${escA(p.id)}',null,this)">↩ Undo</button>`;
  } else {
    actBtns = `<button class="btn-action btn-mylist" onclick="doFeedback('${escA(p.id)}','mylist',this)">＋ My List</button>
               <button class="btn-action btn-notrel" onclick="doFeedback('${escA(p.id)}','not_relevant',this)">✕ Not Relevant</button>`;
  }

  const hasSummary = p.has_summary;
  let summaryBtn = '';
  if (hasSummary) {
    summaryBtn = `<button class="btn-action btn-show-summary" id="dsb-${cid}" onclick="toggleDashSummary('${escA(p.id)}')">📄 Show Summary</button>`;
  } else if (p.confidence === 5) {
    summaryBtn = `<button class="btn-action btn-summarize" id="dsb-${cid}" onclick="doDashSummarize('${escA(p.id)}')">✨ Summarize</button>`;
  } else {
    summaryBtn = `<span class="no-summary-label">📄 No Summary</span>`;
  }

  return `<div class="paper-card${notRel?' dimmed':''}" id="pc-${cid}">
  <div class="paper-card-body" onclick="toggleSummary('${escA(p.id)}')">
    <div class="paper-title">
      <a href="${escA(p.url)}" target="_blank" onclick="event.stopPropagation()">${esc(p.title)}</a>
      <span class="expand-hint" id="eh-${cid}">${expanded?'▲':'▼'}</span>
    </div>
    <div class="paper-meta">
      <span>${esc(authStr)}</span>${p.date?`<span>· ${esc(p.date)}</span>`:''}
    </div>
    <div class="paper-chips">${tagChips}${confBadge(p.confidence)}${srcBadge(p.source)}</div>
  </div>
  <div class="paper-actions">${actBtns}${summaryBtn}</div>
  <div class="dash-summary-panel" id="dsp-${cid}">${hasSummary ? mdToHtml(p.summary) : ''}</div>
  <div class="paper-summary${expanded?' open':''}" id="ps-${cid}">${mdToHtml(p.summary||'')}</div>
</div>`;
}

function toggleSummary(pid) {
  const el = document.getElementById('ps-' + cId(pid));
  const hint = document.getElementById('eh-' + cId(pid));
  if (!el) return;
  const open = el.classList.toggle('open');
  open ? expandedCards.add(pid) : expandedCards.delete(pid);
  if (hint) hint.textContent = open ? '▲' : '▼';
}

function toggleDashSummary(pid) {
  const panel = document.getElementById('dsp-' + cId(pid));
  const btn = document.getElementById('dsb-' + cId(pid));
  if (!panel) return;
  const open = panel.classList.toggle('open');
  if (btn) btn.textContent = open ? '📄 Hide Summary' : '📄 Show Summary';
}

async function doDashSummarize(pid) {
  const btn = document.getElementById('dsb-' + cId(pid));
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = '⏳ Summarizing…';
  try {
    const r = await fetch('/api/summarize/' + encodeURIComponent(pid), {method: 'POST'});
    const data = await r.json();
    if (!r.ok) {
      btn.disabled = false;
      btn.textContent = '✨ Summarize';
      showToast(data.error || 'Error generating summary');
      return;
    }
    const panel = document.getElementById('dsp-' + cId(pid));
    if (panel) { panel.innerHTML = mdToHtml(data.summary); panel.classList.add('open'); }
    btn.textContent = '📄 Hide Summary';
    btn.onclick = () => toggleDashSummary(pid);
    btn.disabled = false;
    const p = allPapers.find(x => x.id === pid);
    if (p) { p.summary = data.summary; p.has_summary = true; }
    showToast('Summary generated ✓');
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = '✨ Summarize'; }
    showToast('Error generating summary');
  }
}

// ============================================================
// FEEDBACK
// ============================================================
async function doFeedback(paperId, action, btn) {
  try {
    const r = await fetch('/api/feedback', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({paper_id: paperId, action}),
    });
    if (!r.ok) { showToast('Error'); return; }
    const p = allPapers.find(x => x.id === paperId);
    if (p) p.feedback = action ? {action} : null;
    if (action === 'mylist') {
      await loadMyList(); renderMyList(); showToast('Added to My List ✓');
    } else if (action === 'not_relevant') {
      showToast('Marked not relevant');
    } else {
      await loadMyList(); renderMyList(); showToast('Feedback removed');
    }
    renderPaperFeed();
  } catch(e) { showToast('Network error'); }
}

// ============================================================
// BADGES
// ============================================================
function confBadge(c) {
  if (!c) return '<span class="badge badge-c0">Unscored</span>';
  const cls = c<=2?'badge-c1':c===3?'badge-c3':c===4?'badge-c4':'badge-c5';
  return `<span class="badge ${cls}">${c}/5</span>`;
}
function srcBadge(s) {
  if (!s) return '';
  const cls = s==='arxiv'?'badge-arxiv':s==='huggingface'?'badge-hf':s==='semantic_scholar'?'badge-ss':'badge-src';
  return `<span class="badge ${cls}">${esc(s)}</span>`;
}
function tagSty(tag) {
  let h = 0;
  for (let i = 0; i < tag.length; i++) { h = ((h<<5)-h)+tag.charCodeAt(i); h|=0; }
  return TAG_PALETTE[Math.abs(h) % TAG_PALETTE.length];
}

// ============================================================
// MY LIST
// ============================================================
function renderMyList() {
  const feed = document.getElementById('mylist-feed');
  const entries = Object.values(myListState).sort((a,b) => (b.added_at||'').localeCompare(a.added_at||''));
  if (!entries.length) {
    feed.innerHTML = `<div class="empty-state"><h3>No papers yet.</h3><p>Go to Dashboard and click ＋ My List on papers you find interesting.</p></div>`;
    return;
  }
  feed.innerHTML = entries.map(mlCardHtml).join('');
}

function mlCardHtml(entry) {
  const pid = entry.paper_id;
  const p = entry.paper || {};
  const authors = p.authors || [];
  const authStr = authors.length <= 3 ? authors.join(', ') : authors.slice(0,3).join(', ') + ' et al.';
  const tags = entry.tags || [];
  const tagsHtml = tags.map((t,i) =>
    `<span class="ml-tag">${esc(t)}<span class="ml-tag-x" onclick="rmMlTag('${escA(pid)}',${i})">×</span></span>`
  ).join('');
  const statusOpts = ['To Read','Priority Read','Read'].map(s =>
    `<option${entry.status===s?' selected':''}>${s}</option>`
  ).join('');
  const showDate = entry.status === 'Read';
  const summary = p.summary || '';
  const isPlaceholder = summary.includes('Summary not generated') || summary.trim() === '';
  const summaryBlock = isPlaceholder
    ? `<button class="btn-action btn-summarize" id="sum-btn-${cId(pid)}" onclick="doSummarize('${escA(pid)}')">✨ Summarize</button>
       <div class="dash-summary-panel" id="sum-area-${cId(pid)}" style="margin:8px 0 0;"></div>`
    : `<button class="btn-action btn-viewsummary" id="sum-btn-${cId(pid)}" onclick="toggleMlSummary('${escA(pid)}')">📄 View Summary</button>
       <div class="dash-summary-panel" id="sum-area-${cId(pid)}" style="margin:8px 0 0;">${mdToHtml(summary)}</div>`;
  return `<div class="mylist-card" id="mlc-${cId(pid)}">
  <button class="btn-rm" onclick="rmFromMyList('${escA(pid)}')">× Remove</button>
  <div class="mylist-title"><a href="${escA(p.url||'#')}" target="_blank">${esc(p.title||'Untitled')}</a></div>
  <div class="mylist-authors">${esc(authStr)}${p.date?' · '+esc(p.date):''}</div>
  <div class="mylist-tags-row" id="mlt-${cId(pid)}">
    ${tagsHtml}
    <input class="ml-tag-inp" type="text" placeholder="Add tag…"
      onkeydown="if(event.key==='Enter'){event.preventDefault();addMlTag('${escA(pid)}',this)}"
      onblur="if(this.value.trim())addMlTag('${escA(pid)}',this)"/>
  </div>
  <div class="mylist-controls">
    <div class="ml-field">
      <span class="ml-field-lbl">Status</span>
      <select class="ml-select" onchange="saveMlEntry('${escA(pid)}',{status:this.value})">${statusOpts}</select>
    </div>
    ${showDate?`<div class="ml-field">
      <span class="ml-field-lbl">Date Read</span>
      <input class="ml-date" type="date" value="${escA(entry.date_read||'')}"
        onchange="saveMlEntry('${escA(pid)}',{date_read:this.value})"/>
    </div>`:''}
  </div>
  <textarea class="ml-notes" placeholder="Notes…"
    onblur="saveMlEntry('${escA(pid)}',{notes:this.value})">${esc(entry.notes||'')}</textarea>
  ${summaryBlock}
</div>`;
}

async function saveMlEntry(pid, updates) {
  try {
    await fetch('/api/mylist/' + encodeURIComponent(pid), {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(updates),
    });
    const e = myListState[pid];
    if (e) {
      Object.assign(e, updates);
      if (updates.status === 'Read' && !e.date_read)
        e.date_read = new Date().toISOString().split('T')[0];
    }
    if ('status' in updates) {
      const card = document.getElementById('mlc-' + cId(pid));
      if (card && e) card.outerHTML = mlCardHtml(e);
    }
  } catch(e2) { showToast('Save error'); }
}

async function rmFromMyList(pid) {
  const card = document.getElementById('mlc-' + cId(pid));
  if (card) card.classList.add('removing');
  setTimeout(async () => {
    try {
      await fetch('/api/mylist/' + encodeURIComponent(pid), {method:'DELETE'});
      delete myListState[pid];
      const p = allPapers.find(x => x.id === pid);
      if (p) p.feedback = null;
      renderMyList(); renderPaperFeed(); showToast('Removed');
    } catch(e) { showToast('Error removing'); }
  }, 370);
}

async function addMlTag(pid, inp) {
  const val = inp.value.trim();
  if (!val) return;
  inp.value = '';
  const e = myListState[pid];
  if (!e) return;
  const tags = [...(e.tags||[])];
  if (!tags.includes(val)) { tags.push(val); await saveMlEntry(pid, {tags}); e.tags = tags; }
  rerenderMlTags(pid);
}

async function rmMlTag(pid, idx) {
  const e = myListState[pid];
  if (!e) return;
  const tags = [...(e.tags||[])];
  tags.splice(idx, 1);
  await saveMlEntry(pid, {tags});
  e.tags = tags;
  rerenderMlTags(pid);
}

function rerenderMlTags(pid) {
  const e = myListState[pid];
  const row = document.getElementById('mlt-' + cId(pid));
  if (!row || !e) return;
  const tags = e.tags || [];
  row.innerHTML = tags.map((t,i) =>
    `<span class="ml-tag">${esc(t)}<span class="ml-tag-x" onclick="rmMlTag('${escA(pid)}',${i})">×</span></span>`
  ).join('') +
  `<input class="ml-tag-inp" type="text" placeholder="Add tag…"
    onkeydown="if(event.key==='Enter'){event.preventDefault();addMlTag('${escA(pid)}',this)}"
    onblur="if(this.value.trim())addMlTag('${escA(pid)}',this)"/>`;
}

// ============================================================
// ON-DEMAND SUMMARIZE
// ============================================================
async function doSummarize(pid) {
  const btn = document.getElementById('sum-btn-' + cId(pid));
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = '⏳ Summarizing…';
  try {
    const r = await fetch('/api/summarize/' + encodeURIComponent(pid), {method: 'POST'});
    const data = await r.json();
    if (!r.ok) {
      btn.disabled = false;
      btn.textContent = '✨ Summarize';
      const errSpan = document.createElement('span');
      errSpan.style.cssText = 'color:var(--danger);font-size:0.75rem;margin-left:8px;';
      errSpan.textContent = data.error || 'Error';
      btn.parentNode.insertBefore(errSpan, btn.nextSibling);
      setTimeout(() => errSpan.remove(), 4000);
      return;
    }
    btn.style.display = 'none';
    const area = document.getElementById('sum-area-' + cId(pid));
    if (area) { area.innerHTML = mdToHtml(data.summary); area.classList.add('open'); }
    showToast('Summary generated ✓');
  } catch(e) {
    if (btn) { btn.disabled = false; btn.textContent = '✨ Summarize'; }
    showToast('Error generating summary');
  }
}

function toggleMlSummary(pid) {
  const area = document.getElementById('sum-area-' + cId(pid));
  const btn = document.getElementById('sum-btn-' + cId(pid));
  if (!area) return;
  const open = area.classList.toggle('open');
  if (btn) btn.textContent = open ? '📄 Hide Summary' : '📄 View Summary';
}

// ============================================================
// CHART
// ============================================================
function initChart() {
  const ctx = document.getElementById('crawl-chart').getContext('2d');
  const labels = crawlHistory.map(e => e.date);
  crawlChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Confidence 5',
          data: crawlHistory.map(e => e.conf5 || 0),
          backgroundColor: '#22c55e',
          borderRadius: 3, borderSkipped: false,
        },
        {
          label: 'Confidence 4',
          data: crawlHistory.map(e => e.conf4 || 0),
          backgroundColor: '#f97316',
          borderRadius: 3, borderSkipped: false,
        },
        {
          label: 'Confidence 3',
          data: crawlHistory.map(e => e.conf3 || 0),
          backgroundColor: '#eab308',
          borderRadius: 3, borderSkipped: false,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          display: true,
          labels: { color: '#6b7080', font: { size: 11 }, boxWidth: 20, padding: 16 },
        },
        tooltip: {
          mode: 'index', intersect: false,
          backgroundColor: '#1a1d27', borderColor: '#2a2d3e', borderWidth: 1,
          titleColor: '#e4e6f0', bodyColor: '#a99bf9',
          callbacks: {
            title: items => items[0].label,
            label: item => ` ${item.dataset.label}: ${item.raw}`,
          },
        },
      },
      scales: {
        x: { stacked: true, ticks: {color:'#6b7080', maxTicksLimit:10, font:{size:10}}, grid: {color:'rgba(42,45,62,0.7)'} },
        y: { stacked: true, ticks: {color:'#6b7080', font:{size:10}, precision:0}, grid: {color:'rgba(42,45,62,0.7)'}, min: 0 },
      },
    },
  });
}

// ============================================================
// PREFERENCES
// ============================================================
async function loadPrefs() {
  try {
    const r = await fetch('/api/preferences');
    applyPrefs(await r.json());
  } catch(e) {}
}
function applyPrefs(prefs) {
  chipData.topics   = prefs.topics   || [];
  chipData.keywords = prefs.keywords || [];
  chipData.authors  = prefs.authors  || [];
  chipData.venues   = prefs.venues   || [];
  renderAllChips();
  (prefs.sources||[]).forEach(s => { const el = document.getElementById('src-'+s); if(el) el.checked=true; });
  if (prefs.days_lookback) document.getElementById('days_lookback').value = prefs.days_lookback;
  if (prefs.max_results_per_source) document.getElementById('max_results_per_source').value = prefs.max_results_per_source;
  const score = prefs.min_relevance_score ?? 0.6;
  document.getElementById('min_relevance_score').value = score;
  document.getElementById('score-display').textContent = score.toFixed(2);
  document.getElementById('slider-val-display').textContent = score.toFixed(2);
  document.getElementById('twitter_search_query').value = prefs.twitter_search_query || '';
}
function gatherPrefs() {
  const sources = SOURCES_ALL.filter(s => { const el=document.getElementById('src-'+s); return el&&el.checked; });
  const tq = document.getElementById('twitter_search_query').value.trim();
  const prefs = {
    topics:[...chipData.topics], keywords:[...chipData.keywords],
    authors:[...chipData.authors], venues:[...chipData.venues],
    sources,
    days_lookback: +document.getElementById('days_lookback').value,
    max_results_per_source: +document.getElementById('max_results_per_source').value,
    min_relevance_score: +parseFloat(document.getElementById('min_relevance_score').value).toFixed(2),
  };
  if (tq) prefs.twitter_search_query = tq;
  return prefs;
}
async function savePrefs() {
  try {
    const r = await fetch('/api/preferences', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(gatherPrefs())});
    showToast(r.ok ? 'Saved ✓' : 'Save failed ✗');
  } catch(e) { showToast('Save failed ✗'); }
}
function renderChips(key) {
  const row = document.getElementById('chips-' + key);
  const items = chipData[key];
  if (!items.length) { row.innerHTML = key==='authors'?'<span class="empty-label">No authors yet</span>':''; return; }
  row.innerHTML = items.map((v,i) =>
    `<span class="chip${key==='authors'?' muted':''}">${esc(v)}<span class="chip-x" onclick="removeChip('${key}',${i})">×</span></span>`
  ).join('');
}
function renderAllChips() { Object.keys(chipData).forEach(renderChips); }
function addChip(key) {
  const inp = document.getElementById('input-' + key);
  const val = inp.value.trim();
  if (!val || chipData[key].includes(val)) { inp.value=''; return; }
  chipData[key].push(val); inp.value=''; renderChips(key);
}
function removeChip(key, idx) { chipData[key].splice(idx,1); renderChips(key); }
function buildSourcesUI() {
  document.getElementById('sources-grid').innerHTML = SOURCES_ALL.map(s =>
    `<label class="source-item"><input type="checkbox" id="src-${s}"/> ${s}</label>`
  ).join('');
}

// ============================================================
// CRAWL
// ============================================================
async function runCrawl() {
  document.getElementById('btn-run').disabled = true;
  setRunning(true);
  try { await fetch('/api/run', {method:'POST'}); } catch(e) {}
  startPolling();
}
function startPolling() { if(pollTimer) clearInterval(pollTimer); pollTimer = setInterval(checkStatus, 3000); }
async function checkStatus() {
  try {
    const data = await (await fetch('/api/status')).json();
    if (data.running) { setRunning(true); }
    else {
      setRunning(false);
      if (pollTimer) { clearInterval(pollTimer); pollTimer=null; }
      document.getElementById('btn-run').disabled = false;
      if (data.last_run) {
        const n = data.paper_count;
        document.getElementById('status-msg').textContent = `✓ Done — ${n} paper${n!==1?'s':''}`;
        await Promise.all([loadPapers(), loadCrawlHistory()]);
        renderPaperFeed();
        if (crawlChart) {
          crawlChart.data.labels = crawlHistory.map(e=>e.date);
          crawlChart.data.datasets[0].data = crawlHistory.map(e=>e.conf5||0);
          crawlChart.data.datasets[1].data = crawlHistory.map(e=>e.conf4||0);
          crawlChart.data.datasets[2].data = crawlHistory.map(e=>e.conf3||0);
          crawlChart.update();
        }
      }
    }
  } catch(e) {}
}
function setRunning(yes) {
  document.getElementById('run-spinner').style.display = yes ? 'block' : 'none';
  document.getElementById('run-label').textContent = yes ? 'Running…' : '🚀 Run Crawl Now';
  if (yes) document.getElementById('status-msg').textContent = 'Running crawl…';
}

// ============================================================
// UTILS
// ============================================================
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function escA(s) { return String(s).replace(/'/g,'&#39;').replace(/"/g,'&quot;'); }
function cId(s) { return String(s).replace(/[^a-zA-Z0-9]/g,'_'); }
function fmtDate(d) {
  if (!d || d==='Unknown') return 'Unknown Date';
  try { return new Date(d+'T00:00:00').toLocaleDateString('en-US',{year:'numeric',month:'long',day:'numeric'}); }
  catch(e) { return d; }
}
function mdToHtml(md) {
  let s = String(md).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  s = s.replace(/^#{2,3}\s+(.+)$/gm,'<h3>$1</h3>');
  s = s.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank">$1</a>');
  s = s.replace(/^---+$/gm,'<hr/>');
  s = s.replace(/\n\n+/g,'</p><p>');
  return '<p>' + s + '</p>';
}
function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes — existing
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML


@app.get("/api/preferences")
async def get_preferences():
    if not PREFS_PATH.exists():
        raise HTTPException(status_code=404, detail="preferences.yaml not found")
    with open(PREFS_PATH) as f:
        data = yaml.safe_load(f) or {}
    return JSONResponse(content=data)


@app.post("/api/preferences")
async def set_preferences(body: dict):
    with open(PREFS_PATH, "w") as f:
        yaml.dump(body, f, default_flow_style=False, allow_unicode=True)
    return {"ok": True}


@app.post("/api/run")
async def run_crawl():
    global _crawl_proc
    with _state_lock:
        if _crawl_proc is not None and _crawl_proc.poll() is None:
            return {"status": "already_running"}
    t = threading.Thread(target=_run_crawl_bg, daemon=True)
    t.start()
    return {"status": "running"}


@app.get("/api/status")
async def get_status():
    with _state_lock:
        running = _crawl_proc is not None and _crawl_proc.poll() is None
        last_run = _last_run
        count = _last_paper_count if last_run else _paper_count()
    return {"running": running, "last_run": last_run, "paper_count": count}


# ---------------------------------------------------------------------------
# Routes — papers
# ---------------------------------------------------------------------------

@app.get("/api/papers")
async def get_papers():
    feedback_data = load_json(FEEDBACK_PATH, {})
    papers = []
    if PAPERS_DIR.exists():
        for path in sorted(PAPERS_DIR.glob("*.md"), key=lambda p: p.name):
            try:
                paper = parse_paper(path)
                fb = feedback_data.get(paper["id"])
                paper["feedback"] = {"action": fb["action"]} if fb else None
                papers.append(paper)
            except Exception:
                continue
    papers.sort(key=lambda p: p["date"], reverse=True)
    return JSONResponse(content=papers)


# ---------------------------------------------------------------------------
# Routes — feedback
# ---------------------------------------------------------------------------

@app.post("/api/feedback")
async def post_feedback(body: dict):
    paper_id = body.get("paper_id")
    action = body.get("action")
    if not paper_id:
        raise HTTPException(status_code=400, detail="paper_id required")

    feedback_data = load_json(FEEDBACK_PATH, {})
    mylist_data = load_json(MYLIST_PATH, {})
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if action is None:
        feedback_data.pop(paper_id, None)
        mylist_data.pop(paper_id, None)
    else:
        feedback_data[paper_id] = {"action": action, "added_at": now}
        if action == "mylist":
            if paper_id not in mylist_data:
                paper_meta = None
                if PAPERS_DIR.exists():
                    for p in PAPERS_DIR.glob("*.md"):
                        try:
                            parsed = parse_paper(p)
                            if parsed["id"] == paper_id:
                                paper_meta = parsed
                                break
                        except Exception:
                            pass
                mylist_data[paper_id] = {
                    "status": "To Read",
                    "date_read": None,
                    "notes": "",
                    "tags": list(paper_meta["tags"]) if paper_meta else [],
                    "added_at": now,
                    "paper": paper_meta,
                }
        elif action == "not_relevant":
            mylist_data.pop(paper_id, None)
            # Delete paper file and its summary file
            if PAPERS_DIR.exists():
                for p in PAPERS_DIR.glob("*.md"):
                    try:
                        parsed = parse_paper(p)
                        if parsed["id"] == paper_id:
                            summary_file = SUMMARIES_DIR / f"{p.stem}.md"
                            if summary_file.exists():
                                summary_file.unlink()
                            p.unlink()
                            break
                    except Exception:
                        pass

    save_json(FEEDBACK_PATH, feedback_data)
    save_json(MYLIST_PATH, mylist_data)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — my list
# ---------------------------------------------------------------------------

@app.get("/api/mylist")
async def get_mylist():
    mylist_data = load_json(MYLIST_PATH, {})
    result = []
    for paper_id, entry in mylist_data.items():
        paper = entry.get("paper") or {}
        title = paper.get("title", "")
        if title:
            stem = _safe_filename(title)
            summary_path = SUMMARIES_DIR / f"{stem}.md"
            if summary_path.exists():
                try:
                    paper = {**paper, "summary": summary_path.read_text(encoding="utf-8").strip(), "has_summary": True}
                except Exception:
                    pass
            else:
                paper = {**paper, "has_summary": False}
        result.append({"paper_id": paper_id, **entry, "paper": paper})
    result.sort(key=lambda e: e.get("added_at", ""), reverse=True)
    return JSONResponse(content=result)


@app.post("/api/mylist/{paper_id}")
async def update_mylist(paper_id: str, body: dict):
    mylist_data = load_json(MYLIST_PATH, {})
    if paper_id not in mylist_data:
        raise HTTPException(status_code=404, detail="Paper not in mylist")
    entry = mylist_data[paper_id]
    if "status" in body:
        entry["status"] = body["status"]
        if body["status"] == "Read" and not entry.get("date_read"):
            entry["date_read"] = datetime.date.today().isoformat()
    if "date_read" in body:
        entry["date_read"] = body["date_read"]
    if "notes" in body:
        entry["notes"] = body["notes"]
    if "tags" in body:
        entry["tags"] = body["tags"]
    save_json(MYLIST_PATH, mylist_data)
    return {"ok": True}


@app.delete("/api/mylist/{paper_id}")
async def delete_mylist(paper_id: str):
    mylist_data = load_json(MYLIST_PATH, {})
    mylist_data.pop(paper_id, None)
    save_json(MYLIST_PATH, mylist_data)
    feedback_data = load_json(FEEDBACK_PATH, {})
    if paper_id in feedback_data and feedback_data[paper_id].get("action") == "mylist":
        feedback_data.pop(paper_id, None)
    save_json(FEEDBACK_PATH, feedback_data)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Routes — crawl history
# ---------------------------------------------------------------------------

@app.get("/api/crawl-history")
async def get_crawl_history():
    history = load_json(CRAWL_HISTORY_PATH, [])
    hist_dict = {e["date"]: e.get("count", 0) for e in history}

    # Compute per-confidence counts by scanning paper files
    conf_by_date: dict = {}
    if PAPERS_DIR.exists():
        for path in PAPERS_DIR.glob("*.md"):
            try:
                text = path.read_text(encoding="utf-8")
                parts = text.split("---\n", 2)
                if len(parts) >= 3:
                    fm = yaml.safe_load(parts[1]) or {}
                    date = str(fm.get("date", "") or "")
                    conf = int(fm.get("confidence", 0) or 0)
                    if date and conf >= 3:
                        if date not in conf_by_date:
                            conf_by_date[date] = {3: 0, 4: 0, 5: 0}
                        if conf in conf_by_date[date]:
                            conf_by_date[date][conf] += 1
            except Exception:
                continue

    today = datetime.date.today()
    result = []
    for i in range(89, -1, -1):
        d = (today - datetime.timedelta(days=i)).isoformat()
        counts = conf_by_date.get(d, {})
        conf3 = counts.get(3, 0)
        conf4 = counts.get(4, 0)
        conf5 = counts.get(5, 0)
        total = conf3 + conf4 + conf5
        # Fall back to crawl_history.json count for dates with no paper files
        if total == 0 and d in hist_dict:
            total = hist_dict[d]
        result.append({"date": d, "total": total, "conf3": conf3, "conf4": conf4, "conf5": conf5})
    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Routes — on-demand summarization
# ---------------------------------------------------------------------------

@app.post("/api/summarize/{paper_id:path}")
async def summarize_paper_on_demand(paper_id: str):
    import os as _os
    api_key = _os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return JSONResponse(status_code=400, content={"error": "ANTHROPIC_API_KEY not set"})

    # Find the paper .md file matching this paper_id
    target_path = None
    target_paper = None
    if PAPERS_DIR.exists():
        for path in PAPERS_DIR.glob("*.md"):
            try:
                parsed = parse_paper(path)
                if parsed["id"] == paper_id:
                    target_path = path
                    target_paper = parsed
                    break
            except Exception:
                continue

    if not target_path or not target_paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    try:
        import importlib.util
        import anthropic as _anthropic
        spec = importlib.util.spec_from_file_location("summarize", BASE_DIR / "summarize.py")
        summarize_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(summarize_mod)  # type: ignore[union-attr]

        client = _anthropic.Anthropic(api_key=api_key)
        summary = summarize_mod.generate_summary(client, {
            "title": target_paper["title"],
            "authors": target_paper["authors"],
            "abstract": target_paper.get("abstract", ""),
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # Write summary to output/summaries/{stem}.md
    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    summary_file = SUMMARIES_DIR / f"{target_path.stem}.md"
    summary_file.write_text(summary, encoding="utf-8")

    # Also update mylist entry if this paper is in mylist
    mylist_data = load_json(MYLIST_PATH, {})
    if paper_id in mylist_data and mylist_data[paper_id].get("paper") is not None:
        mylist_data[paper_id]["paper"]["summary"] = summary
        mylist_data[paper_id]["paper"]["has_summary"] = True
        save_json(MYLIST_PATH, mylist_data)

    return {"ok": True, "summary": summary}


# ---------------------------------------------------------------------------
# Output index
# ---------------------------------------------------------------------------

@app.get("/output", response_class=HTMLResponse)
async def output_index():
    index_path = OUTPUT_DIR / "index.md"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="output/index.md not found — run the crawl first")
    content = index_path.read_text()
    body = md_lib.markdown(content, extensions=["tables", "fenced_code"])
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>ResearchCrawl — Index</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0f1117; color: #e4e6f0;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    padding: 40px 24px 80px; line-height: 1.65;
  }}
  .content {{ max-width: 800px; margin: 0 auto; }}
  h1, h2, h3 {{ font-weight: 700; margin: 1.4em 0 0.5em; line-height: 1.3; }}
  h1 {{ font-size: 1.8rem; }} h2 {{ font-size: 1.3rem; color: #c8cae0; }} h3 {{ font-size: 1.05rem; color: #a8aacc; }}
  p {{ margin: 0.6em 0; }}
  a {{ color: #7c6af7; }} a:hover {{ text-decoration: underline; }}
  code {{ background: #1a1d27; border-radius: 4px; padding: 2px 6px; font-size: 0.88em; }}
  pre {{ background: #1a1d27; border-radius: 8px; padding: 16px; overflow-x: auto; margin: 1em 0; }}
  pre code {{ background: none; padding: 0; }}
  hr {{ border: none; border-top: 1px solid #2a2d3e; margin: 2em 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1em 0; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #2a2d3e; font-size: 0.9rem; }}
  th {{ color: #6b7080; font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }}
  .back {{ display: inline-block; margin-bottom: 28px; color: #7c6af7; font-size: 0.9rem; }}
</style>
</head>
<body>
<div class="content">
  <a href="/" class="back">← Back to ResearchCrawl</a>
  {body}
</div>
</body>
</html>"""
    return html
