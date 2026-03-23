from pydantic import BaseModel, Field
from typing import Optional
import datetime


class PaperNode(BaseModel):
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    date: Optional[str] = None
    url: Optional[str] = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_focal: bool = False
    tags: list[str] = Field(default_factory=list)


class RelationEdge(BaseModel):
    source: str          # paper id
    target: str          # paper id
    relation: str        # human-readable relation description
    strength: float = Field(default=0.5, ge=0.0, le=1.0)


class LiteratureSurveyGraph(BaseModel):
    focal_paper_id: str
    nodes: list[PaperNode]
    edges: list[RelationEdge]
    generated_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


class LiteratureSurvey(BaseModel):
    focal_paper_id: str
    graph: LiteratureSurveyGraph
    survey_text: str           # HTML-rendered academic writeup
    generated_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    paper_count: int = 0
    status: str = "ready"      # "ready" | "generating" | "error"


class SurveyStatusResponse(BaseModel):
    paper_id: str
    status: str                # "not_found" | "generating" | "ready" | "error"
    survey: Optional[LiteratureSurvey] = None
