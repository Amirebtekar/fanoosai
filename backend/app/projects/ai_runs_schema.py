from datetime import datetime
from pydantic import BaseModel

class AIRunRead(BaseModel):
    id: int
    prompt_id: int
    ai_model_id: int
    request_text: str
    response_text: str | None = None
    status: str
    extraction_status: str
    processed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True

class AIRunResult(BaseModel):
    ai_run_id: int
    ai_run_status: str
    extraction_status: str
    brands_found: int
    new_brands: int
    existing_brands: int
    error_message: str | None = None
