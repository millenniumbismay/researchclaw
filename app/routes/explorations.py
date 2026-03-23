import json
import datetime
from fastapi import APIRouter
from app.config import settings
from app.utils import safe_filename

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
