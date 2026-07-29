from pydantic import BaseModel, ConfigDict, Field
from pydantic import field_validator
from typing import List, Optional
from datetime import datetime
from urllib.parse import urlsplit
from app.projects.ai_models_schema import AIModelRead


def normalize_website_url(value: str) -> str:
    value = value.strip()
    parsed = urlsplit(value if "://" in value else f"//{value}")
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("Website URL must use HTTP or HTTPS")
    if not parsed.hostname:
        raise ValueError("A valid website domain is required")
    return parsed.hostname.removeprefix("www.").lower()

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Project name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Project description (optional)"
    )

class ProjectCreate(ProjectBase):
    organization_id: Optional[int] = Field(None, gt=0, description="Organization that owns the project")
    website_url: str = Field(..., max_length=500, description="Project website domain")
    brand_name: str = Field(..., min_length=1, max_length=200, description="Owned brand name")

    @field_validator("website_url")
    @classmethod
    def normalize_website_domain(cls, value: str) -> str:
        return normalize_website_url(value)

    @field_validator("brand_name")
    @classmethod
    def normalize_brand_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Owned brand name is required")
        return value

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Project name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Project description (optional)"
    )
    website_url: Optional[str] = Field(None, max_length=500, description="Project website domain")

    @field_validator("website_url")
    @classmethod
    def normalize_website_domain(cls, value: str | None) -> str | None:
        return normalize_website_url(value) if value is not None else None

class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    website_url: Optional[str] = None
    prompt_count: int = 0
    model_count: int = 0
    created_at: datetime
    updated_at: datetime
    
class ProjectBrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: Optional[str] = Field(None, max_length=500)
    kind: str = Field(pattern="^(owned|competitor)$")

class ProjectBrandRead(ProjectBrandCreate):
    id: int
    brand_id: Optional[int] = None

class ObservedBrandRead(BaseModel):
    brand_id: int
    name: str
    domain: str

# --- Prompt Schemas ---

class PromptBase(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Prompt content")

class PromptCreate(PromptBase):
    model_ids: List[int] = Field(..., min_length=1, description="لیست ID مدل‌های AI انتخاب شده")


class PromptRead(PromptBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None = None
    models: List[AIModelRead] = Field(default_factory=list)
