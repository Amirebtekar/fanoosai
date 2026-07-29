from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AIModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider: str
    model_key: str
    is_active: bool
    created_at: datetime | None = None
