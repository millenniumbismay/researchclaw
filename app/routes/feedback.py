import datetime
from fastapi import APIRouter, HTTPException
from app.config import settings
from app.utils import load_json, save_json
from app.services.paper_service import get_paper_by_id, get_paper_path_by_id
from app.services.paper_content_service import fetch_content_background

router = APIRouter(tags=["feedback"])


@router.post("/api/feedback")
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
                paper_meta = get_paper_by_id(paper_id)
                mylist_data[paper_id] = {
                    "status": "To Read",
                    "date_read": None,
                    "notes": "",
                    "tags": list(paper_meta["tags"]) if paper_meta else [],
                    "added_at": now,
                    "paper": paper_meta,
                }
                # Fetch full paper content from source in background
                paper_url = (paper_meta or {}).get("url", "")
                fetch_content_background(paper_id, paper_url)
        elif action == "not_relevant":
            mylist_data.pop(paper_id, None)
            paper_path = get_paper_path_by_id(paper_id)
            if paper_path:
                summary_file = settings.summaries_dir / f"{paper_path.stem}.md"
                if summary_file.exists():
                    summary_file.unlink()
                paper_path.unlink()

    save_json(settings.feedback_path, feedback_data)
    save_json(settings.mylist_path, mylist_data)
    return {"ok": True}
