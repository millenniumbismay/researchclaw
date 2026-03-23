import datetime
import subprocess
import threading
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
                [".venv/bin/python", script],
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
    """Start crawl in background. Returns 'running' or 'already_running'."""
    global _crawl_proc
    with _state_lock:
        if _crawl_proc is not None and _crawl_proc.poll() is None:
            return "already_running"
    t = threading.Thread(target=_run_crawl_bg, daemon=True)
    t.start()
    return "running"


def get_status() -> dict:
    """Get crawl status."""
    with _state_lock:
        running = _crawl_proc is not None and _crawl_proc.poll() is None
        last_run = _last_run
        count = _last_paper_count if last_run else _paper_count()
    return {"running": running, "last_run": last_run, "paper_count": count}


def get_crawl_history() -> list[dict]:
    """Get 90-day crawl history with confidence breakdowns."""
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
