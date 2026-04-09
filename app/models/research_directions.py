from pydantic import BaseModel, Field
from typing import Optional
import datetime


class CriticalLens(BaseModel):
    dimension: str           # e.g. "Novelty Check", "Methodological Critique"
    title: str               # short punchy title for this specific finding
    insight: str             # 2-4 sentences of critical analysis
    severity: str = "info"   # "info" | "caution" | "concern"


class ResearchDirection(BaseModel):
    title: str
    description: str         # 2-3 sentences
    why_it_matters: str      # 1-2 sentences
    difficulty: str = "medium"  # "low" | "medium" | "high"
    tags: list[str] = Field(default_factory=list)


class CoreDecomposition(BaseModel):
    hypothesis: str
    methodology: str
    experiments: str
    key_findings: str


class ChatMessage(BaseModel):
    role: str                # "user" | "assistant"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


class ResearchDirectionsAnalysis(BaseModel):
    paper_id: str
    core: CoreDecomposition
    critical_lenses: list[CriticalLens] = Field(default_factory=list)
    directions: list[ResearchDirection] = Field(default_factory=list)
    chat_history: list[ChatMessage] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    status: str = "ready"    # "ready" | "generating" | "error"


class ResearchDirectionsStatus(BaseModel):
    paper_id: str
    status: str              # "not_found" | "generating" | "ready" | "error"
    analysis: Optional[ResearchDirectionsAnalysis] = None
    progress: Optional[str] = None


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    updated_directions: Optional[list[ResearchDirection]] = None
