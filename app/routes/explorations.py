import json
import datetime
from fastapi import APIRouter
from app.config import settings
from app.utils import safe_filename
from app.models.literature_survey import SurveyStatusResponse
from app.models.research_directions import (
    ChatRequest,
    ChatResponse,
    ResearchDirectionsStatus,
)
from app.services.literature_survey_service import (
    check_survey_staleness,
    get_survey,
    get_survey_status,
    start_survey_generation,
)
from app.services.research_directions_service import (
    chat_with_analysis,
    get_analysis,
    get_status as get_directions_status,
    start_analysis,
)
from app.services.paper_service import get_all_papers

router = APIRouter(tags=["explorations"])


@router.get("/api/explorations")
async def list_explorations():
    folders = []
    if settings.explorations_dir.exists():
        for f in settings.explorations_dir.iterdir():
            if f.is_dir():
                meta_path = f / "meta.json"
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text())
                    except (json.JSONDecodeError, OSError):
                        continue
                    # Skip incomplete entries (old data without title)
                    if not meta.get("title"):
                        continue
                    folders.append(meta)
    return folders


@router.post("/api/explorations/{paper_id}/init")
async def init_exploration(paper_id: str):
    from app.services.paper_service import get_paper_by_id
    from app.utils import load_json

    folder = settings.explorations_dir / safe_filename(paper_id)
    folder.mkdir(parents=True, exist_ok=True)
    created = False
    notes = folder / "notes.md"
    if not notes.exists():
        notes.touch()
        created = True
    refs = folder / "references.json"
    if not refs.exists():
        refs.write_text("[]")
    meta_path = folder / "meta.json"
    # Always update meta with paper info for left pane rendering
    paper_meta = get_paper_by_id(paper_id)
    mylist_data = load_json(settings.mylist_path, {})
    mylist_entry = mylist_data.get(paper_id, {})
    meta = {
        "paper_id": paper_id,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "title": (paper_meta or {}).get("title", "Untitled"),
        "authors": (paper_meta or {}).get("authors", []),
        "date": (paper_meta or {}).get("date"),
        "status": mylist_entry.get("status", "To Read"),
    }
    # Preserve original created_at if meta already existed
    if meta_path.exists():
        try:
            existing_meta = json.loads(meta_path.read_text())
            meta["created_at"] = existing_meta.get("created_at", meta["created_at"])
        except Exception:
            pass
    meta_path.write_text(json.dumps(meta, indent=2))
    return {"folder": str(folder), "paper_id": paper_id, "created": created}


@router.get("/api/explorations/{paper_id}/survey", response_model=SurveyStatusResponse)
async def get_survey_status_route(paper_id: str):
    status = get_survey_status(paper_id)
    survey = get_survey(paper_id) if status == "ready" else None
    stale = check_survey_staleness(paper_id) if status == "ready" else False
    return SurveyStatusResponse(paper_id=paper_id, status=status, survey=survey, stale=stale)


@router.post("/api/explorations/{paper_id}/survey/generate", response_model=SurveyStatusResponse)
async def generate_survey_route(paper_id: str, force: bool = False):
    all_papers = get_all_papers()
    status = start_survey_generation(paper_id, all_papers, force=force)
    survey = get_survey(paper_id) if status == "ready" else None
    return SurveyStatusResponse(paper_id=paper_id, status=status, survey=survey)


# ============================================================
# Research Directions
# ============================================================

@router.get("/api/explorations/{paper_id}/directions", response_model=ResearchDirectionsStatus)
async def get_directions_route(paper_id: str):
    status = get_directions_status(paper_id)
    analysis = get_analysis(paper_id) if status == "ready" else None
    return ResearchDirectionsStatus(paper_id=paper_id, status=status, analysis=analysis)


@router.post("/api/explorations/{paper_id}/directions/generate", response_model=ResearchDirectionsStatus)
async def generate_directions_route(paper_id: str):
    status = start_analysis(paper_id)
    analysis = get_analysis(paper_id) if status == "ready" else None
    return ResearchDirectionsStatus(paper_id=paper_id, status=status, analysis=analysis)


@router.post("/api/explorations/{paper_id}/directions/chat", response_model=ChatResponse)
async def chat_directions_route(paper_id: str, body: ChatRequest):
    return chat_with_analysis(paper_id, body.message)
