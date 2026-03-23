from pydantic import BaseModel, Field

class UserPreferences(BaseModel):
    topics: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    venues: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    days_lookback: int = 7
    max_results_per_source: int = 50
    min_relevance_score: float = 0.3
    twitter_search_query: str = ""
