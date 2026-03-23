from pydantic import BaseModel

class ExplorationMeta(BaseModel):
    paper_id: str
    created_at: str
    folder: str | None = None

class ExplorationInitResponse(BaseModel):
    paper_id: str
    folder: str
    created: bool
