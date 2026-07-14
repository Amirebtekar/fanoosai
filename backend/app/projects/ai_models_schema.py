from datetime import datetime
from pydantic import BaseModel


class AIModelRead(BaseModel):
    id: int
    name: str
    provider: str
    model_key: str
    is_active: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True
