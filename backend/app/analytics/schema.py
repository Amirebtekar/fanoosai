from datetime import datetime
from pydantic import BaseModel

class DashboardSummary(BaseModel):
    prompt_count: int
    active_model_count: int
    run_count: int
    brand_count: int
    last_successful_run: datetime | None
    successful_run_count: int
    failed_run_count: int

class PromptAnalytics(BaseModel):
    prompt_id: int
    prompt: str
    models: list[str]
    run_count: int
    last_run: datetime | None
    brands_extracted: int
    last_status: str | None

class BrandHistoryItem(BaseModel):
    date: datetime
    rank: int
    ai_model: str
    prompt: str
    ai_run_id: int

class PromptHistoryItem(BaseModel):
    ai_run_id: int
    ai_model: str
    run_date: datetime
    status: str
    extraction_status: str
    brands_count: int

class ProjectHistory(BaseModel):
    total_runs: int
    successful_runs: int
    failed_runs: int
    brands_count: int
    last_successful_run: datetime | None

class LatestRanking(BaseModel):
    brand: str
    domain: str | None
    rank: int
    confidence: float | None
    ai_model: str
    run_date: datetime

class PromptRankingItem(BaseModel):
    brand: str
    domain: str | None
    rank: int
    ai_model: str
    date: datetime

class LatestRun(BaseModel):
    ai_run_id: int
    prompt: str
    ai_model: str
    status: str
    extraction_status: str
    created_at: datetime
    completed_at: datetime | None

class BrandDetails(BaseModel):
    brand_id: int
    name: str
    domain: str | None
    total_appearances: int
    average_rank: float | None
    best_rank: int | None
    worst_rank: int | None
    first_seen: datetime | None
    last_seen: datetime | None

class Page(BaseModel):
    items: list
    page: int
    page_size: int
    total: int
