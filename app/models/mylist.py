from datetime import datetime
from pydantic import BaseModel, Field
from app.models.paper import Paper

class MyListEntry(BaseModel):
    paper_id: str
    paper: Paper | None = None
    status: str = "To Read"
    tags: list[str] = Field(default_factory=list)
    notes: str = ""
    date_read: str | None = None
    added_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class MyListUpdate(BaseModel):
    status: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    date_read: str | None = None
