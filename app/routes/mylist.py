from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.services.mylist_service import get_mylist, update_mylist_entry, remove_from_mylist
from app.config import settings
from app.utils import load_json, save_json

router = APIRouter(tags=["mylist"])


@router.get("/api/mylist")
async def list_mylist():
    return JSONResponse(content=get_mylist())


@router.post("/api/mylist/{paper_id}")
async def update_mylist_item(paper_id: str, body: dict):
    ok = update_mylist_entry(paper_id, body)
    if not ok:
        raise HTTPException(status_code=404, detail="Paper not in mylist")
    return {"ok": True}


@router.delete("/api/mylist/{paper_id}")
async def delete_mylist_item(paper_id: str):
    remove_from_mylist(paper_id)
    # Also clean up feedback if it was a mylist action
    feedback_data = load_json(settings.feedback_path, {})
    if paper_id in feedback_data and feedback_data[paper_id].get("action") == "mylist":
        feedback_data.pop(paper_id, None)
        save_json(settings.feedback_path, feedback_data)
    return {"ok": True}
