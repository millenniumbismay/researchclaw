import datetime
from pathlib import Path
from app.config import settings
from app.utils import load_json, save_json, safe_filename
from app.services.paper_service import parse_paper


def get_mylist() -> list[dict]:
    """Load mylist entries enriched with paper data."""
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


def add_to_mylist(paper_id: str, paper_meta: dict | None) -> dict:
    """Add a paper to mylist. Returns the new entry."""
    mylist_data = load_json(settings.mylist_path, {})
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if paper_id not in mylist_data:
        mylist_data[paper_id] = {
            "status": "To Read",
            "date_read": None,
            "notes": "",
            "tags": list(paper_meta["tags"]) if paper_meta else [],
            "added_at": now,
            "paper": paper_meta,
        }
    save_json(settings.mylist_path, mylist_data)
    return mylist_data[paper_id]


def update_mylist_entry(paper_id: str, updates: dict) -> bool:
    """Update a mylist entry. Returns False if not found."""
    mylist_data = load_json(settings.mylist_path, {})
    if paper_id not in mylist_data:
        return False
    entry = mylist_data[paper_id]
    if "status" in updates:
        entry["status"] = updates["status"]
        if updates["status"] == "Read" and not entry.get("date_read"):
            entry["date_read"] = datetime.date.today().isoformat()
    if "date_read" in updates:
        entry["date_read"] = updates["date_read"]
    if "notes" in updates:
        entry["notes"] = updates["notes"]
    if "tags" in updates:
        entry["tags"] = updates["tags"]
    save_json(settings.mylist_path, mylist_data)
    return True


def remove_from_mylist(paper_id: str) -> None:
    """Remove a paper from mylist."""
    mylist_data = load_json(settings.mylist_path, {})
    mylist_data.pop(paper_id, None)
    save_json(settings.mylist_path, mylist_data)


def update_mylist_summary(paper_id: str, summary: str) -> None:
    """Update the summary for a mylist paper."""
    mylist_data = load_json(settings.mylist_path, {})
    if paper_id in mylist_data and mylist_data[paper_id].get("paper") is not None:
        mylist_data[paper_id]["paper"]["summary"] = summary
        mylist_data[paper_id]["paper"]["has_summary"] = True
        save_json(settings.mylist_path, mylist_data)
