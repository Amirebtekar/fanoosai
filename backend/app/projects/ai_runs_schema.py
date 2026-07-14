from datetime import datetime
from pydantic import BaseModel


class AIRunRead(BaseModel):
    id: int
    prompt_id: int
    ai_model_id: int
    request_text: str
    response_text: str | None = None
    status: str
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class AIRunResult(BaseModel):
    id: int
    ai_model_id: int
    model_key: str
    status: str
    error_message: str | None = None
