import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.config import settings
from app.services.crawl_service import start_crawl, get_status, get_crawl_history

router = APIRouter(tags=["settings"])


@router.get("/api/preferences")
async def get_preferences():
    if not settings.prefs_path.exists():
        raise HTTPException(status_code=404, detail="preferences.yaml not found")
    with open(settings.prefs_path) as f:
        data = yaml.safe_load(f) or {}
    return JSONResponse(content=data)


@router.post("/api/preferences")
async def set_preferences(body: dict):
    with open(settings.prefs_path, "w") as f:
        yaml.dump(body, f, default_flow_style=False, allow_unicode=True)
    return {"ok": True}


@router.post("/api/run")
async def run_crawl():
    status = start_crawl()
    return {"status": status}


@router.get("/api/status")
async def crawl_status():
    return get_status()


@router.get("/api/crawl-history")
async def crawl_history():
    return JSONResponse(content=get_crawl_history())
