import re
import yaml
from pathlib import Path
from app.config import settings
from app.utils import load_json


def _safe_filename(title: str) -> str:
    name = title.lower()
    name = re.sub(r"[^a-z0-9\s-]", "", name)
    name = re.sub(r"\s+", "-", name.strip())
    name = re.sub(r"-+", "-", name)
    return name[:80].rstrip("-")


def parse_paper(path: Path) -> dict:
    """Parse a paper .md file and return a dict representation."""
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


def get_all_papers() -> list[dict]:
    """Load all papers from disk, sorted by date descending."""
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


def get_paper_by_id(paper_id: str) -> dict | None:
    """Find a specific paper by its ID."""
    if not settings.papers_dir.exists():
        return None
    for path in settings.papers_dir.glob("*.md"):
        try:
            parsed = parse_paper(path)
            if parsed["id"] == paper_id:
                return parsed
        except Exception:
            continue
    return None


def get_paper_path_by_id(paper_id: str):
    """Find the file path of a paper by its ID."""
    if not settings.papers_dir.exists():
        return None
    for path in settings.papers_dir.glob("*.md"):
        try:
            parsed = parse_paper(path)
            if parsed["id"] == paper_id:
                return path
        except Exception:
            continue
    return None
