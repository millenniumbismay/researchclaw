import json
import datetime
from fastapi import APIRouter
from app.config import settings
from app.utils import safe_filename
from app.models.literature_survey import SurveyStatusResponse
from app.services.literature_survey_service import (
    get_survey,
    get_survey_status,
    start_survey_generation,
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
                    folders.append(json.loads(meta_path.read_text()))
    return folders


@router.post("/api/explorations/{paper_id}/init")
async def init_exploration(paper_id: str):
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
    meta = folder / "meta.json"
    if not meta.exists():
        meta.write_text(json.dumps(
            {"paper_id": paper_id, "created_at": datetime.datetime.utcnow().isoformat()},
            indent=2
        ))
    return {"folder": str(folder), "paper_id": paper_id, "created": created}


@router.get("/api/explorations/{paper_id}/survey", response_model=SurveyStatusResponse)
async def get_survey_status_route(paper_id: str):
    status = get_survey_status(paper_id)
    survey = get_survey(paper_id) if status == "ready" else None
    return SurveyStatusResponse(paper_id=paper_id, status=status, survey=survey)


@router.post("/api/explorations/{paper_id}/survey/generate", response_model=SurveyStatusResponse)
async def generate_survey_route(paper_id: str):
    all_papers = get_all_papers()
    status = start_survey_generation(paper_id, all_papers)
    survey = get_survey(paper_id) if status == "ready" else None
    return SurveyStatusResponse(paper_id=paper_id, status=status, survey=survey)
