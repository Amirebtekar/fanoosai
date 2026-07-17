from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.projects.ai_models_schema import AIModelRead

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Project name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Project description (optional)"
    )

class ProjectCreate(ProjectBase):
    website_url: Optional[str] = Field(
        None, max_length=500, description="Project website URL (optional)"
    )

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Project name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Project description (optional)"
    )
    website_url: Optional[str] = Field(
        None, max_length=500, description="Project website URL (optional)"
    )

class ProjectRead(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# --- Prompt Schemas ---

class PromptBase(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Prompt content")

class PromptCreate(PromptBase):
    model_ids: Optional[List[int]] = Field(None, description="لیست ID مدل‌های AI انتخاب شده")


class PromptRead(PromptBase):
    id: int
    project_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None = None
    models: List[AIModelRead] = Field(default_factory=list)
    
    class Config:
        from_attributes = True
