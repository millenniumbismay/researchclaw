import os
import importlib.util
from app.config import settings
from app.services.paper_service import get_paper_by_id, get_paper_path_by_id
from app.services.mylist_service import update_mylist_summary


def summarize_paper(paper_id: str) -> dict:
    """
    Summarize a paper on demand. Returns {"ok": True, "summary": "..."} or raises on error.
    Returns {"error": "..."} for user-facing errors.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set"}

    target_path = get_paper_path_by_id(paper_id)
    target_paper = get_paper_by_id(paper_id) if target_path else None

    if not target_path or not target_paper:
        return {"error": "Paper not found", "not_found": True}

    try:
        import anthropic as _anthropic
        spec = importlib.util.spec_from_file_location("summarize", settings.base_dir / "summarize.py")
        summarize_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(summarize_mod)

        client = _anthropic.Anthropic(api_key=api_key)
        summary = summarize_mod.generate_summary(client, {
            "title": target_paper["title"],
            "authors": target_paper["authors"],
            "abstract": target_paper.get("abstract", ""),
            "url": target_paper.get("url", ""),
        })
    except Exception as exc:
        return {"error": str(exc), "server_error": True}

    settings.summaries_dir.mkdir(parents=True, exist_ok=True)
    summary_file = settings.summaries_dir / f"{target_path.stem}.md"
    summary_file.write_text(summary, encoding="utf-8")

    update_mylist_summary(paper_id, summary)

    return {"ok": True, "summary": summary}
