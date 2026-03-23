from pydantic import BaseModel, Field

class Paper(BaseModel):
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    date: str | None = None
    url: str | None = None
    source: str | None = None
    source_tags: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: int = Field(default=0, ge=0, le=5)
    relevance_score: float = 0.0
    abstract: str = ""
    affiliation: str = ""
    summary: str | None = None
    has_summary: bool = False
    feedback: dict | None = None

class PaperListResponse(BaseModel):
    papers: list[Paper]
    total: int
