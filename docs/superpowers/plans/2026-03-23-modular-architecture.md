# ResearchClaw Modular Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor monolithic `ui.py` (1800+ lines) into a product-grade modular architecture with Pydantic models, service layer, split static assets, and Jinja2 templates.

**Architecture:** FastAPI app factory in `app/main.py` with separate route files per domain, service layer between routes and disk I/O, and all frontend split into `static/css/` and `static/js/` files served by FastAPI's StaticFiles. Jinja2 template renders `templates/index.html`.

**Tech Stack:** FastAPI, Pydantic v2, pydantic-settings, Jinja2, uvicorn, Chart.js (CDN), vanilla JS modules (no bundler)

---

## File Map

### New files to create
- `app/__init__.py`
- `app/main.py` — FastAPI factory, middleware, router registration, static/template mounts
- `app/config.py` — Pydantic Settings with all paths
- `app/models/__init__.py`
- `app/models/paper.py` — Paper, PaperListResponse models
- `app/models/mylist.py` — MyListEntry, MyListUpdate models
- `app/models/explorations.py` — ExplorationMeta, ExplorationInitResponse
- `app/models/settings.py` — UserPreferences model
- `app/routes/__init__.py`
- `app/routes/papers.py` — GET /api/papers, POST /api/summarize/{id}
- `app/routes/mylist.py` — GET/POST/DELETE /api/mylist, /api/mylist/{id}
- `app/routes/explorations.py` — GET/POST /api/explorations, /api/explorations/{id}/init
- `app/routes/settings.py` — GET/POST /api/preferences, /api/run, /api/status, /api/crawl-history
- `app/routes/feedback.py` — POST /api/feedback
- `app/services/__init__.py`
- `app/services/paper_service.py` — parse_paper, get_all_papers, get_paper_by_id
- `app/services/mylist_service.py` — load/save mylist, enrich with paper data
- `app/services/summary_service.py` — on-demand summarization
- `app/services/crawl_service.py` — run_crawl subprocess, crawl history
- `app/utils.py` — safe_filename, load_json, save_json
- `templates/index.html` — Jinja2 HTML shell
- `static/css/base.css`
- `static/css/components.css`
- `static/css/dashboard.css`
- `static/css/mylist.css`
- `static/css/explorations.css`
- `static/css/settings.css`
- `static/js/utils.js`
- `static/js/state.js`
- `static/js/api.js`
- `static/js/dashboard.js`
- `static/js/mylist.js`
- `static/js/explorations.js`
- `static/js/settings.js`
- `static/js/app.js`
- `app.py` — thin entrypoint: `from app.main import app`

### Files to modify
- `ui.py` — convert to shim: `from app.main import app`
- `requirements.txt` — add `python-multipart>=0.0.9`, `pydantic-settings>=2.0`, `jinja2>=3.1`

### Files NOT to touch
- `crawl.py`, `summarize.py`, `start_ui.sh`, `run.sh`

---

## Task 1: Python package skeleton + config

**Files:**
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/utils.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add dependencies to requirements.txt**

```
pydantic-settings>=2.0
jinja2>=3.1
# python-multipart is NOT needed — no form endpoints in this app
```

- [ ] **Step 2: Create `app/__init__.py`** (empty)

```python
```

- [ ] **Step 3: Create `app/config.py`**

```python
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RESEARCHCLAW_")

    base_dir: Path = BASE_DIR
    output_dir: Path = BASE_DIR / "output"
    papers_dir: Path = BASE_DIR / "output" / "papers"
    summaries_dir: Path = BASE_DIR / "output" / "summaries"
    explorations_dir: Path = BASE_DIR / "output" / "explorations"
    feedback_path: Path = BASE_DIR / "feedback.json"
    mylist_path: Path = BASE_DIR / "mylist.json"
    prefs_path: Path = BASE_DIR / "preferences.yaml"
    crawl_history_path: Path = BASE_DIR / "crawl_history.json"


settings = Settings()
```

- [ ] **Step 4: Create `app/utils.py`**

```python
import json
import re
from pathlib import Path


def safe_filename(title: str) -> str:
    name = title.lower()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name.strip())
    name = re.sub(r"-+", "-", name)
    return name[:80].rstrip("-")


def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
```

- [ ] **Step 5: Verify syntax**

```bash
cd ~/Projects/researchclaw && .venv/bin/python -m py_compile app/config.py app/utils.py
```

Expected: no output (no errors).

- [ ] **Step 6: Commit**

```bash
git add app/__init__.py app/config.py app/utils.py requirements.txt
git commit -m "feat: add app package skeleton, config, and utils"
```

---

## Task 2: Pydantic models

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/paper.py`
- Create: `app/models/mylist.py`
- Create: `app/models/explorations.py`
- Create: `app/models/settings.py`

- [ ] **Step 1: Create `app/models/__init__.py`** (empty)

- [ ] **Step 2: Create `app/models/paper.py`**

```python
from pydantic import BaseModel, Field


class FeedbackAction(BaseModel):
    action: str


class Paper(BaseModel):
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    date: str | None = None
    url: str | None = None
    source: str | None = None
    source_tags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: int = Field(default=0, ge=0, le=5)
    relevance_score: float = Field(default=0.0)
    abstract: str = ""
    summary: str | None = None
    has_summary: bool = False
    feedback: FeedbackAction | None = None


class PaperListResponse(BaseModel):
    papers: list[Paper]
    total: int


class SummaryResponse(BaseModel):
    ok: bool
    summary: str
```

- [ ] **Step 3: Create `app/models/mylist.py`**

```python
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.paper import Paper


class MyListEntry(BaseModel):
    paper_id: str
    paper: Paper | None = None
    status: str = "To Read"
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    date_read: str | None = None
    added_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class MyListUpdate(BaseModel):
    status: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    date_read: str | None = None
```

- [ ] **Step 4: Create `app/models/explorations.py`**

```python
from pydantic import BaseModel


class ExplorationMeta(BaseModel):
    paper_id: str
    created_at: str
    folder: str | None = None


class ExplorationInitResponse(BaseModel):
    paper_id: str
    folder: str
    created: bool
```

- [ ] **Step 5: Create `app/models/settings.py`**

```python
from pydantic import BaseModel, Field


class UserPreferences(BaseModel):
    topics: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    venues: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    days_lookback: int = 7
    max_results_per_source: int = 50
    min_relevance_score: float = 0.3
    twitter_search_query: str | None = None
```

- [ ] **Step 6: Verify syntax**

```bash
cd ~/Projects/researchclaw && .venv/bin/python -c "from app.models.paper import Paper; from app.models.mylist import MyListEntry; from app.models.explorations import ExplorationMeta; from app.models.settings import UserPreferences; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add app/models/
git commit -m "feat: add Pydantic models for paper, mylist, explorations, settings"
```

---

## Task 3: Service layer

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/paper_service.py`
- Create: `app/services/mylist_service.py`
- Create: `app/services/summary_service.py`
- Create: `app/services/crawl_service.py`

- [ ] **Step 1: Create `app/services/__init__.py`** (empty)

- [ ] **Step 2: Create `app/services/paper_service.py`**

```python
import re
from pathlib import Path

import yaml

from app.config import settings
from app.utils import load_json


def parse_paper(path: Path) -> dict:
    text = path.read_text()
    parts = text.split("---\n", 2)
    if len(parts) >= 3:
        try:
            fm = yaml.safe_load(parts[1]) or {}
        except Exception:
            fm = {}
    else:
        fm = {}

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

    summary_path = settings.summaries_dir / f"{path.stem}.md"
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

    # Note: "affiliation" field from ui.py is intentionally dropped — it was always ""
    # and is not referenced anywhere in the frontend JS.
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
        "summary": summary,
        "has_summary": has_summary,
    }


def get_all_papers() -> list[dict]:
    feedback_data = load_json(settings.feedback_path, {})
    papers = []
    if settings.papers_dir.exists():
        for path in sorted(settings.papers_dir.glob("*.md"), key=lambda p: p.name):
            try:
                paper = parse_paper(path)
                fb = feedback_data.get(paper["id"])
                paper["feedback"] = {"action": fb["action"]} if fb else None
                papers.append(paper)
            except Exception:
                continue
    papers.sort(key=lambda p: p["date"], reverse=True)
    return papers


def get_paper_by_id(paper_id: str) -> tuple[dict | None, Path | None]:
    """Returns (paper_dict, file_path) or (None, None) if not found."""
    if not settings.papers_dir.exists():
        return None, None
    for path in settings.papers_dir.glob("*.md"):
        try:
            parsed = parse_paper(path)
            if parsed["id"] == paper_id:
                return parsed, path
        except Exception:
            continue
    return None, None
```

- [ ] **Step 3: Create `app/services/mylist_service.py`**

```python
import datetime
from pathlib import Path

from app.config import settings
from app.utils import load_json, save_json, safe_filename


def get_mylist() -> list[dict]:
    mylist_data = load_json(settings.mylist_path, {})
    result = []
    for paper_id, entry in mylist_data.items():
        paper = entry.get("paper") or {}
        title = paper.get("title", "")
        if title:
            stem = safe_filename(title)
            summary_path = settings.summaries_dir / f"{stem}.md"
            if summary_path.exists():
                try:
                    paper = {**paper, "summary": summary_path.read_text(encoding="utf-8").strip(), "has_summary": True}
                except Exception:
                    pass
            else:
                paper = {**paper, "has_summary": False}
        result.append({"paper_id": paper_id, **entry, "paper": paper})
    result.sort(key=lambda e: e.get("added_at", ""), reverse=True)
    return result


def update_mylist_entry(paper_id: str, updates: dict) -> bool:
    mylist_data = load_json(settings.mylist_path, {})
    if paper_id not in mylist_data:
        return False
    entry = mylist_data[paper_id]
    if "status" in updates:
        entry["status"] = updates["status"]
        if updates["status"] == "Read" and not entry.get("date_read"):
            entry["date_read"] = datetime.date.today().isoformat()
    for field in ("date_read", "notes", "tags"):
        if field in updates:
            entry[field] = updates[field]
    save_json(settings.mylist_path, mylist_data)
    return True


def delete_mylist_entry(paper_id: str) -> None:
    mylist_data = load_json(settings.mylist_path, {})
    mylist_data.pop(paper_id, None)
    save_json(settings.mylist_path, mylist_data)
    feedback_data = load_json(settings.feedback_path, {})
    if paper_id in feedback_data and feedback_data[paper_id].get("action") == "mylist":
        feedback_data.pop(paper_id, None)
    save_json(settings.feedback_path, feedback_data)
```

- [ ] **Step 4: Create `app/services/summary_service.py`**

```python
import importlib.util
import os
from pathlib import Path

from app.config import settings
from app.services.paper_service import get_paper_by_id
from app.utils import load_json, save_json


def summarize_paper(paper_id: str) -> dict:
    """Returns {'ok': True, 'summary': str} or raises ValueError/RuntimeError."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    paper, target_path = get_paper_by_id(paper_id)
    if not paper or not target_path:
        raise FileNotFoundError(f"Paper not found: {paper_id}")

    import anthropic as _anthropic
    spec = importlib.util.spec_from_file_location("summarize", settings.base_dir / "summarize.py")
    summarize_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(summarize_mod)  # type: ignore[union-attr]

    client = _anthropic.Anthropic(api_key=api_key)
    summary = summarize_mod.generate_summary(client, {
        "title": paper["title"],
        "authors": paper["authors"],
        "abstract": paper.get("abstract", ""),
        "url": paper.get("url", ""),
    })

    settings.summaries_dir.mkdir(parents=True, exist_ok=True)
    summary_file = settings.summaries_dir / f"{target_path.stem}.md"
    summary_file.write_text(summary, encoding="utf-8")

    mylist_data = load_json(settings.mylist_path, {})
    if paper_id in mylist_data and mylist_data[paper_id].get("paper") is not None:
        mylist_data[paper_id]["paper"]["summary"] = summary
        mylist_data[paper_id]["paper"]["has_summary"] = True
        save_json(settings.mylist_path, mylist_data)

    return {"ok": True, "summary": summary}
```

- [ ] **Step 5: Create `app/services/crawl_service.py`**

```python
import datetime
import subprocess
import threading
from pathlib import Path

from app.config import settings
from app.utils import load_json, save_json

_crawl_proc: subprocess.Popen | None = None
_last_run: str | None = None
_last_paper_count: int = 0
_state_lock = threading.Lock()


def _paper_count() -> int:
    return len(list(settings.papers_dir.glob("*.md"))) if settings.papers_dir.exists() else 0


def _update_crawl_history(count: int) -> None:
    history = load_json(settings.crawl_history_path, [])
    today = datetime.date.today().isoformat()
    for e in history:
        if e.get("date") == today:
            e["count"] = count
            save_json(settings.crawl_history_path, history)
            return
    history.append({"date": today, "count": count})
    save_json(settings.crawl_history_path, history)


def _run_crawl_bg() -> None:
    global _crawl_proc, _last_run, _last_paper_count
    try:
        for script in ("crawl.py", "summarize.py"):
            proc = subprocess.Popen(
                [str(settings.base_dir / ".venv" / "bin" / "python"), script],
                cwd=str(settings.base_dir),
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


def start_crawl() -> str:
    global _crawl_proc
    with _state_lock:
        if _crawl_proc is not None and _crawl_proc.poll() is None:
            return "already_running"
    t = threading.Thread(target=_run_crawl_bg, daemon=True)
    t.start()
    return "running"


def get_status() -> dict:
    with _state_lock:
        running = _crawl_proc is not None and _crawl_proc.poll() is None
        last_run = _last_run
        count = _last_paper_count if last_run else _paper_count()
    return {"running": running, "last_run": last_run, "paper_count": count}


def get_crawl_history() -> list[dict]:
    import yaml
    history = load_json(settings.crawl_history_path, [])
    hist_dict = {e["date"]: e.get("count", 0) for e in history}

    conf_by_date: dict = {}
    if settings.papers_dir.exists():
        for path in settings.papers_dir.glob("*.md"):
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
        if total == 0 and d in hist_dict:
            total = hist_dict[d]
        result.append({"date": d, "total": total, "conf3": conf3, "conf4": conf4, "conf5": conf5})
    return result
```

- [ ] **Step 6: Verify syntax**

```bash
cd ~/Projects/researchclaw && .venv/bin/python -m py_compile app/services/paper_service.py app/services/mylist_service.py app/services/summary_service.py app/services/crawl_service.py
```

Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add app/services/
git commit -m "feat: add service layer (paper, mylist, summary, crawl)"
```

---

## Task 4: Route files

**Files:**
- Create: `app/routes/__init__.py`
- Create: `app/routes/papers.py`
- Create: `app/routes/mylist.py`
- Create: `app/routes/explorations.py`
- Create: `app/routes/settings.py`
- Create: `app/routes/feedback.py`

- [ ] **Step 1: Create `app/routes/__init__.py`** (empty)

- [ ] **Step 2: Create `app/routes/papers.py`**

```python
import datetime

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.services.paper_service import get_all_papers
from app.services.summary_service import summarize_paper
from app.config import settings
from app.utils import load_json

router = APIRouter(prefix="/api", tags=["papers"])


@router.get("/papers")
async def list_papers():
    papers = get_all_papers()
    return JSONResponse(content=papers)


@router.post("/summarize/{paper_id:path}")
async def summarize_on_demand(paper_id: str):
    try:
        result = summarize_paper(paper_id)
        return result
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Paper not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

- [ ] **Step 3: Create `app/routes/mylist.py`**

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models.mylist import MyListUpdate
from app.services.mylist_service import get_mylist, update_mylist_entry, delete_mylist_entry

router = APIRouter(prefix="/api", tags=["mylist"])


@router.get("/mylist")
async def list_mylist():
    return JSONResponse(content=get_mylist())


@router.post("/mylist/{paper_id}")
async def update_mylist(paper_id: str, body: MyListUpdate):
    updates = body.model_dump(exclude_none=True)
    if not update_mylist_entry(paper_id, updates):
        raise HTTPException(status_code=404, detail="Paper not in mylist")
    return {"ok": True}


@router.delete("/mylist/{paper_id}")
async def remove_mylist(paper_id: str):
    delete_mylist_entry(paper_id)
    return {"ok": True}
```

- [ ] **Step 4: Create `app/routes/explorations.py`**

```python
import datetime
import json

from fastapi import APIRouter

from app.config import settings
from app.utils import safe_filename

router = APIRouter(prefix="/api", tags=["explorations"])


@router.post("/explorations/{paper_id}/init")
async def init_exploration(paper_id: str):
    safe = safe_filename(paper_id)
    folder = settings.explorations_dir / safe
    folder.mkdir(parents=True, exist_ok=True)
    created = False
    meta = folder / "meta.json"
    if not meta.exists():
        created = True
        (folder / "notes.md").touch()
        (folder / "references.json").write_text("[]")
        meta.write_text(json.dumps({
            "paper_id": paper_id,
            "created_at": datetime.datetime.utcnow().isoformat(),
        }, indent=2))
    return {"folder": str(folder), "paper_id": paper_id, "created": created}


@router.get("/explorations")
async def list_explorations():
    folders = []
    if settings.explorations_dir.exists():
        for f in settings.explorations_dir.iterdir():
            if f.is_dir():
                meta_path = f / "meta.json"
                if meta_path.exists():
                    folders.append(json.loads(meta_path.read_text()))
    return folders
```

- [ ] **Step 5: Create `app/routes/settings.py`**

```python
import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

# Alias as cfg to avoid name collision with this module's own name ("settings")
from app.config import settings as cfg
from app.services.crawl_service import start_crawl, get_status, get_crawl_history

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/preferences")
async def get_preferences():
    if not cfg.prefs_path.exists():
        raise HTTPException(status_code=404, detail="preferences.yaml not found")
    with open(cfg.prefs_path) as f:
        data = yaml.safe_load(f) or {}
    return JSONResponse(content=data)


@router.post("/preferences")
async def set_preferences(body: dict):
    with open(cfg.prefs_path, "w") as f:
        yaml.dump(body, f, default_flow_style=False, allow_unicode=True)
    return {"ok": True}


@router.post("/run")
async def run_crawl():
    status = start_crawl()
    return {"status": status}


@router.get("/status")
async def crawl_status():
    return get_status()


@router.get("/crawl-history")
async def crawl_history():
    return JSONResponse(content=get_crawl_history())
```

- [ ] **Step 6: Create `app/routes/feedback.py`**

```python
import datetime

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.services.paper_service import get_paper_by_id
from app.utils import load_json, save_json

router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback")
async def post_feedback(body: dict):
    paper_id = body.get("paper_id")
    action = body.get("action")
    if not paper_id:
        raise HTTPException(status_code=400, detail="paper_id required")

    feedback_data = load_json(settings.feedback_path, {})
    mylist_data = load_json(settings.mylist_path, {})
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if action is None:
        feedback_data.pop(paper_id, None)
        mylist_data.pop(paper_id, None)
    else:
        feedback_data[paper_id] = {"action": action, "added_at": now}
        if action == "mylist":
            if paper_id not in mylist_data:
                paper_meta, _ = get_paper_by_id(paper_id)
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
            if settings.papers_dir.exists():
                from app.services.paper_service import parse_paper
                for p in settings.papers_dir.glob("*.md"):
                    try:
                        parsed = parse_paper(p)
                        if parsed["id"] == paper_id:
                            summary_file = settings.summaries_dir / f"{p.stem}.md"
                            if summary_file.exists():
                                summary_file.unlink()
                            p.unlink()
                            break
                    except Exception:
                        pass

    save_json(settings.feedback_path, feedback_data)
    save_json(settings.mylist_path, mylist_data)
    return {"ok": True}
```

- [ ] **Step 7: Verify syntax**

```bash
cd ~/Projects/researchclaw && .venv/bin/python -m py_compile app/routes/papers.py app/routes/mylist.py app/routes/explorations.py app/routes/settings.py app/routes/feedback.py
```

Expected: no output.

- [ ] **Step 8: Commit**

```bash
git add app/routes/
git commit -m "feat: add route files for papers, mylist, explorations, settings, feedback"
```

---

## Task 5: App factory (main.py) + entrypoints

**Files:**
- Create: `app/main.py`
- Create: `app.py`
- Modify: `ui.py`

- [ ] **Step 1: Create `app/main.py`**

```python
import markdown as md_lib
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.routes import papers, mylist, explorations, settings as settings_routes, feedback

def create_app() -> FastAPI:
    app = FastAPI(title="ResearchClaw UI")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Ensure required dirs exist
    settings.summaries_dir.mkdir(parents=True, exist_ok=True)
    settings.explorations_dir.mkdir(parents=True, exist_ok=True)

    # Static files + templates
    app.mount("/static", StaticFiles(directory=str(settings.base_dir / "static")), name="static")
    templates = Jinja2Templates(directory=str(settings.base_dir / "templates"))

    # Register routers
    app.include_router(papers.router)
    app.include_router(mylist.router)
    app.include_router(explorations.router)
    app.include_router(settings_routes.router)
    app.include_router(feedback.router)

    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/output", response_class=HTMLResponse)
    async def output_index():
        index_path = settings.output_dir / "index.md"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="output/index.md not found — run the crawl first")
        content = index_path.read_text()
        body = md_lib.markdown(content, extensions=["tables", "fenced_code"])
        return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<style>body{{background:#0f1117;color:#e4e6f0;font-family:system-ui;padding:40px 24px;}}
.content{{max-width:800px;margin:0 auto;}}a{{color:#7c6af7;}}</style>
</head><body><div class="content">{body}</div></body></html>""")

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return app


app = create_app()
```

- [ ] **Step 2: Create `app.py`** (thin entrypoint)

```python
from app.main import app  # noqa: F401
```

- [ ] **Step 3: Modify `ui.py`** — replace the entire file contents with a shim:

Replace everything in `ui.py` with:
```python
"""ResearchClaw UI — shim that imports from the modular app package."""
from app.main import app  # noqa: F401
```

- [ ] **Step 4: Create `static/` and `templates/` directories**

```bash
mkdir -p ~/Projects/researchclaw/static/css ~/Projects/researchclaw/static/js ~/Projects/researchclaw/templates
```

- [ ] **Step 5: Verify syntax**

```bash
cd ~/Projects/researchclaw && .venv/bin/python -m py_compile app/main.py app.py
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add app/main.py app.py ui.py
git commit -m "feat: add app factory, entrypoints, convert ui.py to shim"
```

---

## Task 6: CSS files

Extract all CSS from `ui.py` (lines 193–527) into separate files. The CSS is divided as follows:

- [ ] **Step 1: Create `static/css/base.css`** — CSS variables, reset, body, links, header, tabs, main-content, media queries

```css
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
header {
  display: flex; align-items: stretch; gap: 0;
  padding: 0 0 0 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
  position: sticky; top: 0; z-index: 50;
}
header h1 { font-size: 1.1rem; font-weight: 700; letter-spacing: -0.02em; padding: 18px 24px 18px 0; white-space: nowrap; align-self: center; }
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
.main-content { max-width: 900px; margin: 0 auto; padding: 24px 22px; display: flex; flex-direction: column; gap: 16px; }
#toast { position: fixed; bottom: 70px; right: 20px; background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 9px 16px; font-size: 0.85rem; color: var(--text); opacity: 0; pointer-events: none; transition: opacity 0.22s; z-index: 300; }
#toast.show { opacity: 1; }
@media (max-width: 600px) {
  header { padding: 0 0 0 14px; }
  .main-content { padding: 14px 10px; }
  .tab-btn { padding: 0 10px; font-size: 0.8rem; }
}
```

- [ ] **Step 2: Create `static/css/components.css`** — card, chart, badge, tag-chip, buttons, spinner, empty-state, chip-editor

```css
.card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 20px 22px; }
.card h2 { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 14px; }
.chart-wrap { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px 22px 14px; }
.chart-title { font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 12px; }
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
.empty-state { text-align: center; padding: 56px 20px; color: var(--muted); font-size: 0.88rem; line-height: 1.6; }
.empty-state h3 { font-size: 0.98rem; margin-bottom: 7px; color: var(--text); font-weight: 600; }
.btn { display: inline-flex; align-items: center; gap: 7px; border: none; border-radius: 8px; padding: 9px 20px; font-size: 0.88rem; font-weight: 600; cursor: pointer; transition: background 0.15s, opacity 0.15s; }
.btn:disabled { opacity: 0.45; cursor: not-allowed; }
.btn-save { background: var(--card); color: var(--text); border: 1px solid var(--border); }
.btn-save:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.btn-run { background: var(--accent); color: #fff; }
.btn-run:hover:not(:disabled) { background: var(--accent-dim); }
.btn-small { background: var(--accent); color: #fff; border: none; border-radius: 6px; padding: 7px 16px; font-size: 0.86rem; font-weight: 600; cursor: pointer; white-space: nowrap; transition: background 0.15s; }
.btn-small:hover { background: var(--accent-dim); }
.btn-action { padding: 4px 12px; border-radius: 5px; font-size: 0.78rem; font-weight: 600; cursor: pointer; border: 1px solid; transition: background 0.15s; line-height: 1.5; }
.btn-mylist { background: rgba(124,106,247,0.1); color: var(--accent); border-color: rgba(124,106,247,0.3); }
.btn-mylist:hover:not(:disabled) { background: rgba(124,106,247,0.2); }
.btn-mylist.in-list { background: rgba(106,247,160,0.08); color: var(--success); border-color: rgba(106,247,160,0.25); cursor: default; }
.btn-notrel { background: rgba(247,106,106,0.08); color: var(--danger); border-color: rgba(247,106,106,0.25); }
.btn-notrel:hover { background: rgba(247,106,106,0.16); }
.btn-undo { background: rgba(107,112,128,0.1); color: var(--muted); border-color: rgba(107,112,128,0.25); }
.btn-undo:hover { background: rgba(107,112,128,0.2); color: var(--text); }
.btn-explore { background: rgba(251,191,36,0.1); color: #fbbf24; border-color: rgba(251,191,36,0.3); }
.btn-explore:hover:not(:disabled) { background: rgba(251,191,36,0.2); }
.btn-summarize { background: rgba(34,197,94,0.1); color: #22c55e; border-color: rgba(34,197,94,0.3); }
.btn-summarize:hover:not(:disabled) { background: rgba(34,197,94,0.2); }
.btn-summarize:disabled { opacity: 0.6; cursor: wait; }
.btn-viewsummary { background: rgba(107,112,128,0.1); color: var(--muted); border-color: rgba(107,112,128,0.25); }
.btn-viewsummary:hover { background: rgba(107,112,128,0.2); color: var(--text); }
.btn-show-summary { background: rgba(124,106,247,0.08); color: var(--accent); border-color: rgba(124,106,247,0.25); }
.btn-show-summary:hover { background: rgba(124,106,247,0.18); }
.no-summary-label { font-size: 0.78rem; color: var(--muted); opacity: 0.55; padding: 4px 10px; }
.status-msg { font-size: 0.82rem; color: var(--muted); margin-right: 6px; }
.spinner { width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.25); border-top-color: #fff; border-radius: 50%; animation: spin 0.7s linear infinite; display: none; }
@keyframes spin { to { transform: rotate(360deg); } }
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
```

- [ ] **Step 3: Create `static/css/dashboard.css`** — filter bar, date header, paper card, paper summary panels

```css
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
  color: var(--text); font-size: 0.8rem; padding: 5px 8px; outline: none; color-scheme: dark;
}
.filter-date:focus { border-color: var(--accent); }
.filter-src-lbl { display: inline-flex; align-items: center; gap: 5px; font-size: 0.8rem; color: var(--muted); cursor: pointer; }
.filter-src-lbl input[type=checkbox] { accent-color: var(--accent); cursor: pointer; }
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
.date-header { font-size: 0.76rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); padding: 6px 0 4px; margin-top: 6px; }
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
.paper-actions { display: flex; gap: 6px; padding: 0 16px 12px; flex-wrap: wrap; }
.paper-summary { display: none; padding: 11px 16px 13px; font-size: 0.84rem; line-height: 1.68; color: #adb0cc; border-top: 1px solid var(--border); word-break: break-word; }
.paper-summary.open { display: block; }
.paper-summary h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 8px 0 3px; }
.paper-summary p { margin-bottom: 5px; }
.paper-summary a { color: var(--accent); }
.paper-summary em { color: var(--muted); font-size: 0.78rem; }
.dash-summary-panel { display: none; margin: 0 16px 12px; padding: 12px; background: rgba(255,255,255,0.025); border-left: 3px solid var(--accent); border-radius: 0 4px 4px 0; font-size: 0.84rem; line-height: 1.68; color: #adb0cc; word-break: break-word; }
.dash-summary-panel.open { display: block; }
.dash-summary-panel h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 8px 0 3px; }
.dash-summary-panel p { margin-bottom: 5px; }
.dash-summary-panel a { color: var(--accent); }
```

- [ ] **Step 4: Create `static/css/mylist.css`**

```css
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
.ml-select, .ml-date { background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 0.83rem; padding: 5px 9px; outline: none; color-scheme: dark; }
.ml-select:focus, .ml-date:focus { border-color: var(--accent); }
.ml-notes { width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 0.83rem; padding: 7px 10px; resize: vertical; min-height: 52px; outline: none; font-family: var(--font); }
.ml-notes:focus { border-color: var(--accent); }
.btn-rm { position: absolute; top: 12px; right: 12px; background: none; border: 1px solid var(--border); border-radius: 5px; color: var(--muted); font-size: 0.77rem; padding: 3px 8px; cursor: pointer; transition: background 0.15s, color 0.15s, border-color 0.15s; }
.btn-rm:hover { background: rgba(247,106,106,0.1); color: var(--danger); border-color: rgba(247,106,106,0.3); }
.ml-summary-area { margin-top: 10px; font-size: 0.84rem; line-height: 1.68; color: #adb0cc; word-break: break-word; border-top: 1px solid var(--border); padding-top: 10px; }
.ml-summary-area p { margin-bottom: 5px; }
.ml-summary-area h3 { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 8px 0 3px; }
```

- [ ] **Step 5: Create `static/css/explorations.css`**

```css
.explorations-layout {
  display: grid;
  grid-template-columns: 240px 1fr 260px;
  /* Note: ui.py had 52px here but the header is actually 58px tall (.tab-btn height: 58px).
     58px is correct and fixes a subtle overflow bug in the original. Intentional change. */
  height: calc(100vh - 58px);
  overflow: hidden;
}
.exp-left {
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: 12px 0;
  background: var(--card);
}
.exp-middle {
  overflow-y: auto;
  padding: 24px 28px;
}
.exp-right {
  border-left: 1px solid var(--border);
  overflow-y: auto;
  background: var(--card);
  padding: 0;
}
.exp-right-header {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--muted);
  padding: 14px 16px 10px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--card);
  z-index: 1;
}
.exp-paper-item {
  padding: 12px 16px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}
.exp-paper-item:hover { background: rgba(124,106,247,0.06); }
.exp-paper-item.active {
  border-left-color: var(--accent);
  background: rgba(124,106,247,0.1);
}
.exp-paper-title {
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--text);
  line-height: 1.4;
  margin-bottom: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.exp-paper-meta { font-size: 0.74rem; color: var(--muted); line-height: 1.4; }
.exp-paper-status {
  display: inline-block;
  margin-top: 5px;
  padding: 1px 7px;
  border-radius: var(--chip-radius);
  font-size: 0.7rem;
  font-weight: 500;
  background: rgba(124,106,247,0.12);
  color: var(--accent);
  border: 1px solid rgba(124,106,247,0.25);
}
.exp-related-item {
  padding: 11px 16px;
  border-bottom: 1px solid var(--border);
  transition: background 0.15s;
}
.exp-related-item:hover { background: rgba(255,255,255,0.03); }
.exp-related-title { font-size: 0.81rem; font-weight: 500; color: var(--text); line-height: 1.4; margin-bottom: 3px; }
.exp-related-title a { color: inherit; }
.exp-related-title a:hover { color: var(--accent); }
.exp-related-meta { font-size: 0.72rem; color: var(--muted); }
```

- [ ] **Step 6: Create `static/css/settings.css`**

```css
.sources-grid { display: flex; flex-wrap: wrap; gap: 14px; }
.source-item { display: flex; align-items: center; gap: 8px; font-size: 0.9rem; cursor: pointer; }
.source-item input[type=checkbox] { width: 17px; height: 17px; accent-color: var(--accent); cursor: pointer; }
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
```

- [ ] **Step 7: Commit**

```bash
git add static/css/
git commit -m "feat: split CSS into base, components, dashboard, mylist, explorations, settings"
```

---

## Task 7: JavaScript files

- [ ] **Step 1: Create `static/js/utils.js`**

```javascript
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
```

- [ ] **Step 2: Create `static/js/state.js`**

```javascript
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
let activeExplorationPid = null;

function tagSty(tag) {
  let h = 0;
  for (let i = 0; i < tag.length; i++) { h = ((h<<5)-h)+tag.charCodeAt(i); h|=0; }
  return TAG_PALETTE[Math.abs(h) % TAG_PALETTE.length];
}
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
```

- [ ] **Step 3: Create `static/js/api.js`**

```javascript
async function apiFetchPapers() {
  const r = await fetch('/api/papers');
  return r.json();
}
async function apiFetchMyList() {
  const r = await fetch('/api/mylist');
  return r.json();
}
async function apiFetchCrawlHistory() {
  const r = await fetch('/api/crawl-history');
  return r.json();
}
async function apiFetchPrefs() {
  const r = await fetch('/api/preferences');
  return r.json();
}
async function apiSavePrefs(prefs) {
  return fetch('/api/preferences', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(prefs)});
}
async function apiPostFeedback(paperId, action) {
  return fetch('/api/feedback', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({paper_id:paperId, action})});
}
async function apiUpdateMyList(paperId, updates) {
  return fetch('/api/mylist/'+encodeURIComponent(paperId), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(updates)});
}
async function apiDeleteMyList(paperId) {
  return fetch('/api/mylist/'+encodeURIComponent(paperId), {method:'DELETE'});
}
async function apiSummarize(paperId) {
  const r = await fetch('/api/summarize/'+encodeURIComponent(paperId), {method:'POST'});
  return {r, data: await r.json()};
}
async function apiRunCrawl() {
  return fetch('/api/run', {method:'POST'});
}
async function apiFetchStatus() {
  const r = await fetch('/api/status');
  return r.json();
}
async function apiInitExploration(paperId) {
  return fetch('/api/explorations/'+encodeURIComponent(paperId)+'/init', {method:'POST'});
}
```

- [ ] **Step 4: Create `static/js/dashboard.js`**

```javascript
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
    `<label class="filter-src-lbl"><input type="checkbox" checked value="${esc(s)}" onchange="toggleSrcFilter('${esc(s)}',this.checked)"/> ${esc(s)}</label>`
  ).join('');
  const menu = document.getElementById('tag-filter-menu');
  menu.innerHTML = allTags.size === 0
    ? '<div style="padding:7px 8px;font-size:0.78rem;color:var(--muted)">No tags yet</div>'
    : [...allTags].sort().map(t =>
        `<label class="tag-opt"><input type="checkbox" value="${esc(t)}" onchange="toggleTagFilter('${escA(t)}',this.checked)"/> ${esc(t)}</label>`
      ).join('');
  updateTagBtn();
}
function toggleTagMenu() { document.getElementById('tag-filter-menu').classList.toggle('open'); }
function toggleTagFilter(tag, on) { on ? activeTagFilters.add(tag) : activeTagFilters.delete(tag); updateTagBtn(); applyFilters(); }
function updateTagBtn() { const n=activeTagFilters.size; document.getElementById('tag-filter-btn').textContent=n?`Tags (${n}) ▾`:'Tags ▾'; }
function toggleSrcFilter(src, on) { on ? activeSourceFilters.add(src) : activeSourceFilters.delete(src); applyFilters(); }
function getFiltered() {
  const q = document.getElementById('filter-search').value.trim().toLowerCase();
  const minC = +document.getElementById('filter-conf').value;
  const from = document.getElementById('filter-from').value;
  const to   = document.getElementById('filter-to').value;
  return allPapers.filter(p => {
    if (activeSourceFilters.size && !activeSourceFilters.has(p.source)) return false;
    if (activeTagFilters.size) { const pt=new Set(p.tags||[]); if(![...activeTagFilters].some(t=>pt.has(t))) return false; }
    if (p.confidence < minC) return false;
    if (from && p.date < from) return false;
    if (to   && p.date > to)   return false;
    if (q) { const hay=((p.title||'')+' '+(p.authors||[]).join(' ')).toLowerCase(); if(!hay.includes(q)) return false; }
    return true;
  });
}
function applyFilters() { renderPaperFeed(); }
function renderPaperFeed() {
  const feed = document.getElementById('paper-feed');
  const papers = getFiltered();
  if (!papers.length) { feed.innerHTML='<div class="empty-state"><h3>No papers found.</h3><p>Try adjusting filters or run the crawl.</p></div>'; return; }
  const byDate = {};
  papers.forEach(p => { const d=p.date||'Unknown'; (byDate[d]||(byDate[d]=[])).push(p); });
  const dates = Object.keys(byDate).sort((a,b)=>b.localeCompare(a));
  feed.innerHTML = dates.map(d => `<div class="date-header">${fmtDate(d)}</div>`+byDate[d].map(paperCardHtml).join('')).join('');
}
function paperCardHtml(p) {
  const fb = p.feedback ? p.feedback.action : null;
  const inML = !!myListState[p.id];
  const notRel = fb === 'not_relevant';
  const authors = p.authors || [];
  const authStr = authors.length <= 3 ? authors.join(', ') : authors.slice(0,3).join(', ')+' et al.';
  const tagChips = (p.tags||[]).map(t=>{const s=tagSty(t);return `<span class="tag-chip" style="background:${s.bg};color:${s.color};border-color:${s.border}">${esc(t)}</span>`;}).join('');
  const expanded = expandedCards.has(p.id);
  const cid = cId(p.id);
  let actBtns = '';
  if (fb==='mylist'||inML) { actBtns=`<button class="btn-action btn-mylist in-list" disabled>✓ In My List</button>`; }
  else if (notRel) { actBtns=`<button class="btn-action btn-undo" onclick="doFeedback('${escA(p.id)}',null,this)">↩ Undo</button>`; }
  else { actBtns=`<button class="btn-action btn-mylist" onclick="doFeedback('${escA(p.id)}','mylist',this)">＋ My List</button><button class="btn-action btn-notrel" onclick="doFeedback('${escA(p.id)}','not_relevant',this)">✕ Not Relevant</button>`; }
  const hasSummary = p.has_summary;
  let summaryBtn = '';
  if (hasSummary) { summaryBtn=`<button class="btn-action btn-show-summary" id="dsb-${cid}" onclick="toggleDashSummary('${escA(p.id)}')">📄 Show Summary</button>`; }
  else if (p.confidence===5) { summaryBtn=`<button class="btn-action btn-summarize" id="dsb-${cid}" onclick="doDashSummarize('${escA(p.id)}')">✨ Summarize</button>`; }
  else { summaryBtn=`<span class="no-summary-label">📄 No Summary</span>`; }
  return `<div class="paper-card${notRel?' dimmed':''}" id="pc-${cid}">
  <div class="paper-card-body" onclick="toggleSummary('${escA(p.id)}')">
    <div class="paper-title"><a href="${escA(p.url)}" target="_blank" onclick="event.stopPropagation()">${esc(p.title)}</a><span class="expand-hint" id="eh-${cid}">${expanded?'▲ Abstract':'▼ Abstract'}</span></div>
    <div class="paper-meta"><span>${esc(authStr)}</span>${p.date?`<span>· ${esc(p.date)}</span>`:''}</div>
    <div class="paper-chips">${tagChips}${confBadge(p.confidence)}${srcBadge(p.source)}</div>
  </div>
  <div class="paper-actions">${actBtns}${summaryBtn}</div>
  <div class="dash-summary-panel" id="dsp-${cid}">${hasSummary?mdToHtml(p.summary):''}</div>
  <div class="paper-summary${expanded?' open':''}" id="ps-${cid}"><p style="margin:0;white-space:pre-wrap">${esc(p.abstract||'')}</p></div>
</div>`;
}
function toggleSummary(pid) {
  const el=document.getElementById('ps-'+cId(pid));
  const hint=document.getElementById('eh-'+cId(pid));
  if(!el) return;
  const open=el.classList.toggle('open');
  open?expandedCards.add(pid):expandedCards.delete(pid);
  if(hint) hint.textContent=open?'▲':'▼';
}
function toggleDashSummary(pid) {
  const panel=document.getElementById('dsp-'+cId(pid));
  const btn=document.getElementById('dsb-'+cId(pid));
  if(!panel) return;
  const open=panel.classList.toggle('open');
  if(btn) btn.textContent=open?'📄 Hide Summary':'📄 Show Summary';
}
async function doDashSummarize(pid) {
  const btn=document.getElementById('dsb-'+cId(pid));
  if(!btn) return;
  btn.disabled=true; btn.textContent='⏳ Summarizing…';
  try {
    const {r,data}=await apiSummarize(pid);
    if(!r.ok){btn.disabled=false;btn.textContent='✨ Summarize';showToast(data.error||'Error generating summary');return;}
    const panel=document.getElementById('dsp-'+cId(pid));
    if(panel){panel.innerHTML=mdToHtml(data.summary);panel.classList.add('open');}
    btn.textContent='📄 Hide Summary';
    btn.onclick=()=>toggleDashSummary(pid);
    btn.disabled=false;
    const p=allPapers.find(x=>x.id===pid);
    if(p){p.summary=data.summary;p.has_summary=true;}
    showToast('Summary generated ✓');
  } catch(e){if(btn){btn.disabled=false;btn.textContent='✨ Summarize';}showToast('Error generating summary');}
}
async function doFeedback(paperId, action, btn) {
  try {
    const r=await apiPostFeedback(paperId,action);
    if(!r.ok){showToast('Error');return;}
    const p=allPapers.find(x=>x.id===paperId);
    if(p) p.feedback=action?{action}:null;
    if(action==='mylist'){const data=await apiFetchMyList();myListState={};data.forEach(e=>{myListState[e.paper_id]=e;});renderMyList();showToast('Added to My List ✓');}
    else if(action==='not_relevant'){showToast('Marked not relevant');}
    else{const data=await apiFetchMyList();myListState={};data.forEach(e=>{myListState[e.paper_id]=e;});renderMyList();showToast('Feedback removed');}
    renderPaperFeed();
  } catch(e){showToast('Network error');}
}
function initChart() {
  const ctx=document.getElementById('crawl-chart').getContext('2d');
  const labels=crawlHistory.map(e=>e.date);
  crawlChart=new Chart(ctx,{type:'bar',data:{labels,datasets:[
    {label:'Confidence 5',data:crawlHistory.map(e=>e.conf5||0),backgroundColor:'#22c55e',borderRadius:3,borderSkipped:false},
    {label:'Confidence 4',data:crawlHistory.map(e=>e.conf4||0),backgroundColor:'#f97316',borderRadius:3,borderSkipped:false},
    {label:'Confidence 3',data:crawlHistory.map(e=>e.conf3||0),backgroundColor:'#eab308',borderRadius:3,borderSkipped:false},
  ]},options:{responsive:true,plugins:{legend:{display:true,labels:{color:'#6b7080',font:{size:11},boxWidth:20,padding:16}},tooltip:{mode:'index',intersect:false,backgroundColor:'#1a1d27',borderColor:'#2a2d3e',borderWidth:1,titleColor:'#e4e6f0',bodyColor:'#a99bf9',callbacks:{title:items=>items[0].label,label:item=>` ${item.dataset.label}: ${item.raw}`}}},scales:{x:{stacked:true,ticks:{color:'#6b7080',maxTicksLimit:10,font:{size:10}},grid:{color:'rgba(42,45,62,0.7)'}},y:{stacked:true,ticks:{color:'#6b7080',font:{size:10},precision:0},grid:{color:'rgba(42,45,62,0.7)'},min:0}}}});
}
```

- [ ] **Step 5: Create `static/js/mylist.js`**

```javascript
function renderMyList() {
  renderExplorationsList();
  const feed=document.getElementById('mylist-feed');
  const entries=Object.values(myListState).sort((a,b)=>(b.added_at||'').localeCompare(a.added_at||''));
  if(!entries.length){feed.innerHTML=`<div class="empty-state"><h3>No papers yet.</h3><p>Go to Dashboard and click ＋ My List on papers you find interesting.</p></div>`;return;}
  feed.innerHTML=entries.map(mlCardHtml).join('');
}
function mlCardHtml(entry) {
  const pid=entry.paper_id;
  const p=entry.paper||{};
  const authors=p.authors||[];
  const authStr=authors.length<=3?authors.join(', '):authors.slice(0,3).join(', ')+' et al.';
  const tags=entry.tags||[];
  const tagsHtml=tags.map((t,i)=>`<span class="ml-tag">${esc(t)}<span class="ml-tag-x" onclick="rmMlTag('${escA(pid)}',${i})">×</span></span>`).join('');
  const statusOpts=['To Read','Priority Read','Read'].map(s=>`<option${entry.status===s?' selected':''}>${s}</option>`).join('');
  const showDate=entry.status==='Read';
  const summary=p.summary||'';
  const isPlaceholder=summary.includes('Summary not generated')||summary.trim()==='';
  const summaryBlock=isPlaceholder
    ?`<button class="btn-action btn-summarize" id="sum-btn-${cId(pid)}" onclick="doSummarize('${escA(pid)}')">✨ Summarize</button><div class="dash-summary-panel" id="sum-area-${cId(pid)}" style="margin:8px 0 0;"></div>`
    :`<button class="btn-action btn-viewsummary" id="sum-btn-${cId(pid)}" onclick="toggleMlSummary('${escA(pid)}')">📄 View Summary</button><div class="dash-summary-panel" id="sum-area-${cId(pid)}" style="margin:8px 0 0;">${mdToHtml(summary)}</div>`;
  return `<div class="mylist-card" id="mlc-${cId(pid)}">
  <button class="btn-rm" onclick="rmFromMyList('${escA(pid)}')">× Remove</button>
  <div class="mylist-title"><a href="${escA(p.url||'#')}" target="_blank">${esc(p.title||'Untitled')}</a></div>
  <div class="mylist-authors">${esc(authStr)}${p.date?' · '+esc(p.date):''}</div>
  <div class="mylist-tags-row" id="mlt-${cId(pid)}">${tagsHtml}<input class="ml-tag-inp" type="text" placeholder="Add tag…" onkeydown="if(event.key==='Enter'){event.preventDefault();addMlTag('${escA(pid)}',this)}" onblur="if(this.value.trim())addMlTag('${escA(pid)}',this)"/></div>
  <div class="mylist-controls">
    <div class="ml-field"><span class="ml-field-lbl">Status</span><select class="ml-select" onchange="saveMlEntry('${escA(pid)}',{status:this.value})">${statusOpts}</select></div>
    ${showDate?`<div class="ml-field"><span class="ml-field-lbl">Date Read</span><input class="ml-date" type="date" value="${escA(entry.date_read||'')}" onchange="saveMlEntry('${escA(pid)}',{date_read:this.value})"/></div>`:''}
  </div>
  <textarea class="ml-notes" placeholder="Notes…" onblur="saveMlEntry('${escA(pid)}',{notes:this.value})">${esc(entry.notes||'')}</textarea>
  ${summaryBlock}
  <button class="btn-action btn-explore" onclick="openExploration('${escA(pid)}')">🔭 Explore</button>
</div>`;
}
async function saveMlEntry(pid, updates) {
  try {
    await apiUpdateMyList(pid, updates);
    const e=myListState[pid];
    if(e){Object.assign(e,updates);if(updates.status==='Read'&&!e.date_read)e.date_read=new Date().toISOString().split('T')[0];}
    if('status' in updates){const card=document.getElementById('mlc-'+cId(pid));if(card&&e)card.outerHTML=mlCardHtml(e);}
  } catch(e2){showToast('Save error');}
}
async function rmFromMyList(pid) {
  const card=document.getElementById('mlc-'+cId(pid));
  if(card) card.classList.add('removing');
  setTimeout(async()=>{
    try{await apiDeleteMyList(pid);delete myListState[pid];const p=allPapers.find(x=>x.id===pid);if(p)p.feedback=null;renderMyList();renderPaperFeed();showToast('Removed');}
    catch(e){showToast('Error removing');}
  },370);
}
async function addMlTag(pid,inp) {
  const val=inp.value.trim();if(!val)return;inp.value='';
  const e=myListState[pid];if(!e)return;
  const tags=[...(e.tags||[])];
  if(!tags.includes(val)){tags.push(val);await saveMlEntry(pid,{tags});e.tags=tags;}
  rerenderMlTags(pid);
}
async function rmMlTag(pid,idx) {
  const e=myListState[pid];if(!e)return;
  const tags=[...(e.tags||[])];tags.splice(idx,1);
  await saveMlEntry(pid,{tags});e.tags=tags;rerenderMlTags(pid);
}
function rerenderMlTags(pid) {
  const e=myListState[pid];const row=document.getElementById('mlt-'+cId(pid));if(!row||!e)return;
  const tags=e.tags||[];
  row.innerHTML=tags.map((t,i)=>`<span class="ml-tag">${esc(t)}<span class="ml-tag-x" onclick="rmMlTag('${escA(pid)}',${i})">×</span></span>`).join('')
    +`<input class="ml-tag-inp" type="text" placeholder="Add tag…" onkeydown="if(event.key==='Enter'){event.preventDefault();addMlTag('${escA(pid)}',this)}" onblur="if(this.value.trim())addMlTag('${escA(pid)}',this)"/>`;
}
async function doSummarize(pid) {
  const btn=document.getElementById('sum-btn-'+cId(pid));if(!btn)return;
  btn.disabled=true;btn.textContent='⏳ Summarizing…';
  try {
    const{r,data}=await apiSummarize(pid);
    if(!r.ok){btn.disabled=false;btn.textContent='✨ Summarize';const errSpan=document.createElement('span');errSpan.style.cssText='color:var(--danger);font-size:0.75rem;margin-left:8px;';errSpan.textContent=data.error||'Error';btn.parentNode.insertBefore(errSpan,btn.nextSibling);setTimeout(()=>errSpan.remove(),4000);return;}
    btn.style.display='none';const area=document.getElementById('sum-area-'+cId(pid));if(area){area.innerHTML=mdToHtml(data.summary);area.classList.add('open');}showToast('Summary generated ✓');
  } catch(e){if(btn){btn.disabled=false;btn.textContent='✨ Summarize';}showToast('Error generating summary');}
}
function toggleMlSummary(pid) {
  const area=document.getElementById('sum-area-'+cId(pid));const btn=document.getElementById('sum-btn-'+cId(pid));if(!area)return;
  const open=area.classList.toggle('open');if(btn)btn.textContent=open?'📄 Hide Summary':'📄 View Summary';
}
```

- [ ] **Step 6: Create `static/js/explorations.js`**

```javascript
function renderExplorationsList() {
  const pane=document.getElementById('exp-left-pane');if(!pane)return;
  const entries=Object.values(myListState).sort((a,b)=>(b.added_at||'').localeCompare(a.added_at||''));
  if(!entries.length){pane.innerHTML='<div class="empty-state" style="padding:20px 14px;font-size:0.83rem;">No papers in My List yet.</div>';return;}
  pane.innerHTML=entries.map(e=>{
    const p=e.paper||{};const pid=e.paper_id;
    const authors=(p.authors||[]);
    const authStr=authors.length<=2?authors.join(', '):authors[0]+' et al.';
    const isActive=pid===activeExplorationPid;
    return '<div class="exp-paper-item'+(isActive?' active':'')+'" id="expi-'+cId(pid)+'" onclick="selectExplorationPaper('+JSON.stringify(pid)+')">'
      +'<div class="exp-paper-title">'+esc(p.title||'Untitled')+'</div>'
      +'<div class="exp-paper-meta">'+esc(authStr)+(p.date?' · '+esc(p.date):'')+'</div>'
      +(e.status?'<span class="exp-paper-status">'+esc(e.status)+'</span>':'')
      +'</div>';
  }).join('');
}
function selectExplorationPaper(pid) {
  if(activeExplorationPid){const prev=document.getElementById('expi-'+cId(activeExplorationPid));if(prev)prev.classList.remove('active');}
  activeExplorationPid=pid;
  const cur=document.getElementById('expi-'+cId(pid));if(cur)cur.classList.add('active');
  const mid=document.getElementById('exp-middle-pane');
  const entry=myListState[pid]||{};const p=entry.paper||{};
  mid.innerHTML='<div style="color:var(--muted);font-size:0.88rem;text-align:center;padding:60px 20px;">'
    +'<h2 style="color:var(--text);font-size:1.1rem;margin-bottom:8px;">'+esc(p.title||'Untitled')+'</h2>'
    +'<p>Exploration dashboard coming soon.</p></div>';
  renderRelatedPapers(pid);
}
function renderRelatedPapers(pid) {
  const list=document.getElementById('exp-related-list');
  const entry=myListState[pid]||{};const p=entry.paper||{};
  const myTags=(entry.tags||[]).map(t=>t.toLowerCase());
  const myAuthors=(p.authors||[]).map(a=>a.toLowerCase());
  const myTitle=(p.title||'').toLowerCase();
  const candidates=allPapers.filter(x=>x.id!==pid).map(x=>{
    let score=0;
    const xTags=(x.tags||[]).map(t=>t.toLowerCase());
    const xAuthors=(x.authors||[]).map(a=>a.toLowerCase());
    const xTitle=(x.title||'').toLowerCase();
    myTags.forEach(t=>{if(xTags.includes(t))score+=3;});
    myAuthors.forEach(a=>{if(xAuthors.includes(a))score+=2;});
    const myWords=myTitle.split(/\W+/).filter(w=>w.length>4);
    myWords.forEach(w=>{if(xTitle.includes(w))score+=1;});
    return{paper:x,score};
  }).filter(x=>x.score>0).sort((a,b)=>b.score-a.score).slice(0,15);
  if(!candidates.length){list.innerHTML='<div class="empty-state" style="padding:20px 12px;font-size:0.82rem;"><p>No related papers found.<br>Add tags to your paper for better matches.</p></div>';return;}
  list.innerHTML=candidates.map(function(item){
    const x=item.paper;const authors=(x.authors||[]);
    const authStr=authors.length<=2?authors.join(', '):authors[0]+' et al.';
    return '<div class="exp-related-item">'
      +'<div class="exp-related-title"><a href="'+escA(x.url||'#')+'" target="_blank">'+esc(x.title||'Untitled')+'</a></div>'
      +'<div class="exp-related-meta">'+esc(authStr)+(x.date?' · '+esc(x.date):'')+'</div>'
      +'</div>';
  }).join('');
}
function openExploration(pid) {
  switchTab('explorations');
  apiInitExploration(pid).catch(()=>{});
  selectExplorationPaper(pid);
}
```

- [ ] **Step 7: Create `static/js/settings.js`**

```javascript
async function loadPrefs() {
  try { applyPrefs(await apiFetchPrefs()); } catch(e) {}
}
function applyPrefs(prefs) {
  chipData.topics=prefs.topics||[];chipData.keywords=prefs.keywords||[];chipData.authors=prefs.authors||[];chipData.venues=prefs.venues||[];
  renderAllChips();
  (prefs.sources||[]).forEach(s=>{const el=document.getElementById('src-'+s);if(el)el.checked=true;});
  if(prefs.days_lookback) document.getElementById('days_lookback').value=prefs.days_lookback;
  if(prefs.max_results_per_source) document.getElementById('max_results_per_source').value=prefs.max_results_per_source;
  const score=prefs.min_relevance_score??0.3;
  document.getElementById('min_relevance_score').value=score;
  document.getElementById('score-display').textContent=score.toFixed(2);
  document.getElementById('slider-val-display').textContent=score.toFixed(2);
  document.getElementById('twitter_search_query').value=prefs.twitter_search_query||'';
}
function gatherPrefs() {
  const sources=SOURCES_ALL.filter(s=>{const el=document.getElementById('src-'+s);return el&&el.checked;});
  const tq=document.getElementById('twitter_search_query').value.trim();
  const prefs={
    topics:[...chipData.topics],keywords:[...chipData.keywords],authors:[...chipData.authors],venues:[...chipData.venues],
    sources,
    days_lookback:+document.getElementById('days_lookback').value,
    max_results_per_source:+document.getElementById('max_results_per_source').value,
    min_relevance_score:+parseFloat(document.getElementById('min_relevance_score').value).toFixed(2),
  };
  if(tq) prefs.twitter_search_query=tq;
  return prefs;
}
async function savePrefs() {
  try{const r=await apiSavePrefs(gatherPrefs());showToast(r.ok?'Saved ✓':'Save failed ✗');}catch(e){showToast('Save failed ✗');}
}
function renderChips(key) {
  const row=document.getElementById('chips-'+key);const items=chipData[key];
  if(!items.length){row.innerHTML=key==='authors'?'<span class="empty-label">No authors yet</span>':'';return;}
  row.innerHTML=items.map((v,i)=>`<span class="chip${key==='authors'?' muted':''}">${esc(v)}<span class="chip-x" onclick="removeChip('${key}',${i})">×</span></span>`).join('');
}
function renderAllChips(){Object.keys(chipData).forEach(renderChips);}
function addChip(key){const inp=document.getElementById('input-'+key);const val=inp.value.trim();if(!val||chipData[key].includes(val)){inp.value='';return;}chipData[key].push(val);inp.value='';renderChips(key);}
function removeChip(key,idx){chipData[key].splice(idx,1);renderChips(key);}
function buildSourcesUI(){document.getElementById('sources-grid').innerHTML=SOURCES_ALL.map(s=>`<label class="source-item"><input type="checkbox" id="src-${s}"/> ${s}</label>`).join('');}
async function runCrawl(){
  document.getElementById('btn-run').disabled=true;setRunning(true);
  try{await apiRunCrawl();}catch(e){}
  startPolling();
}
function startPolling(){if(pollTimer)clearInterval(pollTimer);pollTimer=setInterval(checkStatus,3000);}
async function checkStatus(){
  try{
    const data=await apiFetchStatus();
    if(data.running){setRunning(true);}
    else{
      setRunning(false);if(pollTimer){clearInterval(pollTimer);pollTimer=null;}
      document.getElementById('btn-run').disabled=false;
      if(data.last_run){
        const n=data.paper_count;
        document.getElementById('status-msg').textContent=`✓ Done — ${n} paper${n!==1?'s':''}`;
        const papers=await apiFetchPapers();allPapers=papers;buildFilterOptions();renderPaperFeed();
        crawlHistory=await apiFetchCrawlHistory();
        if(crawlChart){crawlChart.data.labels=crawlHistory.map(e=>e.date);crawlChart.data.datasets[0].data=crawlHistory.map(e=>e.conf5||0);crawlChart.data.datasets[1].data=crawlHistory.map(e=>e.conf4||0);crawlChart.data.datasets[2].data=crawlHistory.map(e=>e.conf3||0);crawlChart.update();}
      }
    }
  }catch(e){}
}
function setRunning(yes){
  document.getElementById('run-spinner').style.display=yes?'block':'none';
  document.getElementById('run-label').textContent=yes?'Running…':'🚀 Run Crawl Now';
  if(yes)document.getElementById('status-msg').textContent='Running crawl…';
}
```

- [ ] **Step 8: Create `static/js/app.js`**

```javascript
function switchTab(name) {
  document.querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  document.querySelector('[data-tab="'+name+'"]').classList.add('active');
}

document.addEventListener('DOMContentLoaded', async () => {
  buildSourcesUI();
  ['topics','keywords','authors','venues'].forEach(k=>{
    document.getElementById('input-'+k).addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();addChip(k);}});
  });
  document.addEventListener('click',e=>{if(!e.target.closest('.tag-filter-wrap'))document.getElementById('tag-filter-menu').classList.remove('open');});

  const [papers, mylist, history] = await Promise.all([apiFetchPapers(), apiFetchMyList(), apiFetchCrawlHistory()]);
  allPapers = papers;
  mylist.forEach(e=>{myListState[e.paper_id]=e;});
  crawlHistory = history;

  await loadPrefs();
  buildFilterOptions();
  renderPaperFeed();
  renderMyList();
  initChart();
  checkStatus();
});
```

- [ ] **Step 9: Commit**

```bash
git add static/js/
git commit -m "feat: split JS into utils, state, api, dashboard, mylist, explorations, settings, app"
```

---

## Task 8: Jinja2 HTML template

**Files:**
- Create: `templates/index.html`

- [ ] **Step 1: Create `templates/index.html`**

This is the full HTML shell with all inline JS/CSS removed, replaced by `<link>` and `<script>` tags.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>ResearchClaw</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<link rel="stylesheet" href="/static/css/base.css"/>
<link rel="stylesheet" href="/static/css/components.css"/>
<link rel="stylesheet" href="/static/css/dashboard.css"/>
<link rel="stylesheet" href="/static/css/mylist.css"/>
<link rel="stylesheet" href="/static/css/explorations.css"/>
<link rel="stylesheet" href="/static/css/settings.css"/>
</head>
<body>

<header>
  <h1>🔬 ResearchClaw</h1>
  <nav class="tab-nav">
    <button class="tab-btn active" data-tab="dashboard" onclick="switchTab('dashboard')">📊 Dashboard</button>
    <button class="tab-btn" data-tab="mylist" onclick="switchTab('mylist')">📚 My List</button>
    <button class="tab-btn" data-tab="explorations" onclick="switchTab('explorations')">🔭 Explorations</button>
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

<!-- EXPLORATIONS -->
<div id="tab-explorations" class="tab-pane">
  <div class="explorations-layout">
    <div class="exp-left" id="exp-left-pane"></div>
    <div class="exp-middle" id="exp-middle-pane">
      <div class="empty-state">
        <h3>Select a paper</h3>
        <p>Click a paper on the left to open its exploration dashboard.</p>
      </div>
    </div>
    <div class="exp-right" id="exp-right-pane">
      <div class="exp-right-header">Related Papers</div>
      <div id="exp-related-list">
        <div class="empty-state" style="padding:24px 12px;">
          <p>Select a paper to see related work.</p>
        </div>
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
          <label>Min relevance score (<span id="score-display">0.3</span>)</label>
          <div class="slider-row">
            <input type="range" id="min_relevance_score" min="0" max="1" step="0.05"
                   oninput="document.getElementById('score-display').textContent=(+this.value).toFixed(2);document.getElementById('slider-val-display').textContent=(+this.value).toFixed(2)"/>
            <span class="slider-val" id="slider-val-display">0.30</span>
          </div>
        </div>
        <div class="field full-width">
          <label for="twitter_search_query">Twitter search query</label>
          <input type="text" id="twitter_search_query" placeholder="Auto-generated from topics/keywords"/>
        </div>
      </div>
    </div>
    <div class="card" style="display:flex;gap:12px;justify-content:flex-end;align-items:center;flex-wrap:wrap;padding:16px 24px;">
      <span class="status-msg" id="status-msg"></span>
      <button class="btn btn-save" onclick="savePrefs()">💾 Save Preferences</button>
      <button class="btn btn-run" id="btn-run" onclick="runCrawl()">
        <span class="spinner" id="run-spinner"></span>
        <span id="run-label">🚀 Run Crawl Now</span>
      </button>
    </div>
  </div>
</div>

<div id="toast"></div>

<script src="/static/js/utils.js"></script>
<script src="/static/js/state.js"></script>
<script src="/static/js/api.js"></script>
<script src="/static/js/dashboard.js"></script>
<script src="/static/js/mylist.js"></script>
<script src="/static/js/explorations.js"></script>
<script src="/static/js/settings.js"></script>
<script src="/static/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add templates/index.html
git commit -m "feat: add Jinja2 HTML template shell"
```

---

## Task 9: Install dependencies + verify + smoke test

- [ ] **Step 1: Install new dependencies**

```bash
cd ~/Projects/researchclaw && .venv/bin/pip install pydantic-settings jinja2 python-multipart
```

Expected: Successfully installed (or already satisfied).

- [ ] **Step 2: Compile-check all new Python files**

```bash
cd ~/Projects/researchclaw && .venv/bin/python -m py_compile \
  app/__init__.py app/config.py app/utils.py \
  app/models/paper.py app/models/mylist.py app/models/explorations.py app/models/settings.py \
  app/services/paper_service.py app/services/mylist_service.py app/services/summary_service.py app/services/crawl_service.py \
  app/routes/papers.py app/routes/mylist.py app/routes/explorations.py app/routes/settings.py app/routes/feedback.py \
  app/main.py app.py ui.py && echo "ALL OK"
```

Expected: `ALL OK`

- [ ] **Step 3: Start the server**

```bash
cd ~/Projects/researchclaw && bash start_ui.sh &
sleep 3
curl -s http://localhost:7337/ | head -5
```

Expected: HTML response starting with `<!DOCTYPE html>`

- [ ] **Step 4: Smoke-test API endpoints**

```bash
curl -s http://localhost:7337/api/papers | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Papers: {len(d)}')"
curl -s http://localhost:7337/api/mylist | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'MyList: {len(d)}')"
curl -s http://localhost:7337/api/preferences | python3 -c "import sys,json; d=json.load(sys.stdin); print('Prefs OK:', list(d.keys())[:3])"
curl -s http://localhost:7337/api/crawl-history | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'History entries: {len(d)}')"
curl -s http://localhost:7337/api/status | python3 -c "import sys,json; d=json.load(sys.stdin); print('Status:', d)"
```

Expected: each prints meaningful output without errors.

- [ ] **Step 5: Kill server**

```bash
pkill -f "uvicorn ui:app" || true
```

- [ ] **Step 6: Final commit**

```bash
git add requirements.txt
git commit -m "refactor: modular architecture with Pydantic models, service layer, and split static assets"
```

- [ ] **Step 7: Run the openclaw notification**

```bash
openclaw system event --text "Done: ResearchClaw refactored to modular architecture" --mode now
```

---

## Notes for the implementer

- The `ui.py` shim keeps `start_ui.sh` working unchanged (it runs `uvicorn ui:app`).
- `app.py` is an additional thin entrypoint for `uvicorn app:app` if preferred.
- `app/routes/settings.py` uses `from app.config import settings as cfg` (already applied in the code block above) to avoid the module name collision.
- In `app/main.py`, the import `from app.routes import settings as settings_routes` avoids shadowing `cfg` from config.
- The `MyListUpdate` Pydantic model in routes/mylist.py uses `body.model_dump(exclude_none=True)` — this requires Pydantic v2.
- CSS `colorscheme: dark` → correct property name is `color-scheme: dark` (fixed in the CSS files above).
- Tasks must be executed in order. The server start in Task 9 Step 3 requires the `static/` and `templates/` directories from Tasks 6–8.
