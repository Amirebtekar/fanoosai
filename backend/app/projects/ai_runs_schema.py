from datetime import datetime
from pydantic import BaseModel, ConfigDict

class AIRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

class AIRunResult(BaseModel):
    ai_run_id: int
    ai_run_status: str
    extraction_status: str
    brands_found: int
    new_brands: int
    existing_brands: int
    error_message: str | None = None


class PromptModelExecutionAvailability(BaseModel):
    model_id: int
    model_name: str
    can_run: bool
    claim_source: str | None = None
