from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.services.paper_service import get_all_papers
from app.services.summary_service import summarize_paper

router = APIRouter(tags=["papers"])


@router.get("/api/papers")
async def list_papers():
    papers = get_all_papers()
    return JSONResponse(content=papers)


@router.post("/api/summarize/{paper_id:path}")
async def summarize_paper_endpoint(paper_id: str):
    result = summarize_paper(paper_id)
    if result.get("not_found"):
        raise HTTPException(status_code=404, detail="Paper not found")
    if result.get("server_error"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result
