from typing import List
import csv
import io
import json
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.fastapi_users import fastapi_users
from app.core.config import settings
from app.database.models import AIModel, AIRun, Project, Prompt, PromptModel, UserTable
from app.dependencies import get_session
from app.projects.ai_models_schema import AIModelRead
from app.projects.schema import PromptRead
from app.repositories.system_settings_repository import (
    DOMAIN_INSTRUCTION_KEY,
    EXTRACTION_MODEL_KEY,
    EXTRACTION_PROMPT_KEY,
    SystemSettingsRepository,
)
from app.services.ai_run_service import DOMAIN_FORMAT_INSTRUCTION
from app.services.brand_extraction_service import EXTRACTION_PROMPT
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/admin", tags=["admin"])

require_superuser = fastapi_users.current_user(active=True, superuser=True)


class AdminPromptRead(PromptRead):
    model_config = ConfigDict(from_attributes=True)

    project_name: str = ""


class AdminCostItem(BaseModel):
    id: int
    created_at: datetime
    model: str
    provider: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_irt: float | None
    status: str


class AdminOverview(BaseModel):
    users: int
    projects: int
    prompts_active: int
    prompts_archived: int
    models_active: int
    models_inactive: int
    runs_total: int
    runs_failed: int


def _admin_prompt_read(prompt: Prompt) -> AdminPromptRead:
    return AdminPromptRead(
        id=prompt.id,
        project_id=prompt.project_id,
        text=prompt.text,
        is_active=prompt.is_active,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        last_run_at=prompt.last_run_at,
        models=[AIModelRead.model_validate(link.model) for link in prompt.models],
        project_name=prompt.project.name if prompt.project else "",
    )


@router.get("/costs", response_model=List[AdminCostItem])
async def admin_costs(
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> List[AdminCostItem]:
    rows = (await session.execute(
        select(AIRun.id, AIRun.created_at, AIModel.name, AIRun.provider_used, AIRun.prompt_tokens, AIRun.completion_tokens, AIRun.total_tokens, AIRun.cost_irt, AIRun.status)
        .join(AIModel, AIModel.id == AIRun.ai_model_id)
        .order_by(AIRun.created_at.desc())
    )).all()
    return [AdminCostItem(id=row[0], created_at=row[1], model=row[2], provider=row[3], prompt_tokens=row[4], completion_tokens=row[5], total_tokens=row[6], cost_irt=row[7], status=row[8]) for row in rows]


@router.get("/overview", response_model=AdminOverview)
async def admin_overview(
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> AdminOverview:
    async def count(model, *conditions):
        stmt = select(func.count()).select_from(model)
        for condition in conditions:
            stmt = stmt.where(condition)
        return (await session.execute(stmt)).scalar_one()

    return AdminOverview(
        users=await count(UserTable),
        projects=await count(Project),
        prompts_active=await count(Prompt, Prompt.is_active.is_(True)),
        prompts_archived=await count(Prompt, Prompt.is_active.is_(False)),
        models_active=await count(AIModel, AIModel.is_active.is_(True)),
        models_inactive=await count(AIModel, AIModel.is_active.is_(False)),
        runs_total=await count(AIRun),
        runs_failed=await count(AIRun, AIRun.status != "success"),
    )


class ExtractionSettings(BaseModel):
    extraction_prompt: str
    extraction_model: str
    domain_format_instruction: str


@router.get("/extraction-settings", response_model=ExtractionSettings)
async def get_extraction_settings(
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> ExtractionSettings:
    repo = SystemSettingsRepository(session)
    return ExtractionSettings(
        extraction_prompt=(await repo.get(EXTRACTION_PROMPT_KEY)) or EXTRACTION_PROMPT,
        extraction_model=(await repo.get(EXTRACTION_MODEL_KEY)) or settings.BRAND_EXTRACTION_MODEL,
        domain_format_instruction=(await repo.get(DOMAIN_INSTRUCTION_KEY)) or DOMAIN_FORMAT_INSTRUCTION,
    )


@router.put("/extraction-settings", response_model=ExtractionSettings)
async def update_extraction_settings(
    payload: ExtractionSettings,
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> ExtractionSettings:
    if "{response_text}" not in payload.extraction_prompt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="پرامپت استخراج باید شامل {response_text} باشد")
    if not payload.extraction_model.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="مدل تحلیل‌گر نمی‌تواند خالی باشد")
    repo = SystemSettingsRepository(session)
    await repo.set(EXTRACTION_PROMPT_KEY, payload.extraction_prompt)
    await repo.set(EXTRACTION_MODEL_KEY, payload.extraction_model.strip())
    await repo.set(DOMAIN_INSTRUCTION_KEY, payload.domain_format_instruction)
    return payload


@router.post("/extraction-settings/reset", response_model=ExtractionSettings)
async def reset_extraction_settings(
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> ExtractionSettings:
    repo = SystemSettingsRepository(session)
    await repo.set(EXTRACTION_PROMPT_KEY, EXTRACTION_PROMPT)
    await repo.set(EXTRACTION_MODEL_KEY, settings.BRAND_EXTRACTION_MODEL)
    await repo.set(DOMAIN_INSTRUCTION_KEY, DOMAIN_FORMAT_INSTRUCTION)
    return ExtractionSettings(
        extraction_prompt=EXTRACTION_PROMPT,
        extraction_model=settings.BRAND_EXTRACTION_MODEL,
        domain_format_instruction=DOMAIN_FORMAT_INSTRUCTION,
    )


@router.get("/prompts", response_model=List[AdminPromptRead])
async def list_all_prompts(
    include_archived: bool = Query(False, description="شامل پرامپت‌های بایگانی‌شده"),
    search: str = Query("", max_length=200, description="جستجو در متن پرامپت یا نام پروژه"),
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> List[AdminPromptRead]:
    stmt = (
        select(Prompt)
        .options(selectinload(Prompt.models).selectinload(PromptModel.model), selectinload(Prompt.project))
        .join(Project, Prompt.project_id == Project.id)
        .order_by(Prompt.updated_at.desc())
    )
    if not include_archived:
        stmt = stmt.where(Prompt.is_active.is_(True))
    if search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(Prompt.text.ilike(term) | Project.name.ilike(term))
    prompts = (await session.execute(stmt)).scalars().all()
    return [_admin_prompt_read(p) for p in prompts]


class AdminReferenceItem(BaseModel):
    url: str
    project_id: int
    project_name: str
    prompt_id: int
    prompt: str
    ai_model_id: int
    ai_model: str
    run_date: datetime


class AdminReferencesPage(BaseModel):
    items: List[AdminReferenceItem]
    page: int
    page_size: int
    total: int


@router.get("/references", response_model=AdminReferencesPage)
async def admin_references(
    project_id: int | None = Query(None, gt=0),
    ai_model_id: int | None = Query(None, gt=0),
    search: str = Query("", max_length=500, description="جستجو در آدرس رفرنس"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> AdminReferencesPage:
    stmt = (
        select(Prompt.id, Prompt.text, AIModel.id, AIModel.name, AIRun.created_at, AIRun.response_text, Project.id, Project.name)
        .select_from(AIRun)
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .join(AIModel, AIModel.id == AIRun.ai_model_id)
        .join(Project, Project.id == Prompt.project_id)
        .where(AIRun.status == "success", AIRun.response_text.is_not(None))
        .order_by(AIRun.created_at.desc(), AIRun.id.desc())
    )
    if project_id is not None:
        stmt = stmt.where(Prompt.project_id == project_id)
    if ai_model_id is not None:
        stmt = stmt.where(AIRun.ai_model_id == ai_model_id)

    # ponytail: sources live in response JSON; normalize into a table if this scan becomes slow.
    items = []
    seen = set()
    for (prompt_id_value, prompt_text, model_id, model_name, run_date, response_text,
         proj_id, proj_name) in (await session.execute(stmt)).all():
        try:
            sources = json.loads(response_text).get("sources", [])
        except (AttributeError, TypeError, json.JSONDecodeError):
            continue
        if not isinstance(sources, list):
            continue
        for url in sources:
            if not isinstance(url, str):
                continue
            try:
                parsed = urlsplit(url)
            except ValueError:
                continue
            key = (url, prompt_id_value, model_id)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or key in seen:
                continue
            if search.strip() and search.strip().lower() not in url.lower():
                continue
            seen.add(key)
            items.append(AdminReferenceItem(
                url=url,
                project_id=proj_id,
                project_name=proj_name,
                prompt_id=prompt_id_value,
                prompt=prompt_text,
                ai_model_id=model_id,
                ai_model=model_name,
                run_date=run_date,
            ))

    start = (page - 1) * page_size
    return AdminReferencesPage(
        items=items[start:start + page_size],
        page=page,
        page_size=page_size,
        total=len(items),
    )


@router.get("/references/export")
async def export_admin_references(
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> Response:
    stmt = (
        select(Prompt.id, Prompt.text, AIModel.id, AIModel.name, AIRun.created_at, AIRun.response_text, Project.id, Project.name)
        .select_from(AIRun)
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .join(AIModel, AIModel.id == AIRun.ai_model_id)
        .join(Project, Project.id == Prompt.project_id)
        .where(AIRun.status == "success", AIRun.response_text.is_not(None))
        .order_by(AIRun.created_at.desc(), AIRun.id.desc())
    )
    rows = []
    seen = set()
    for prompt_id_value, prompt_text, model_id, model_name, run_date, response_text, proj_id, proj_name in (await session.execute(stmt)).all():
        try:
            sources = json.loads(response_text).get("sources", [])
        except (AttributeError, TypeError, json.JSONDecodeError):
            continue
        for url in sources if isinstance(sources, list) else []:
            if not isinstance(url, str):
                continue
            try:
                parsed = urlsplit(url)
            except ValueError:
                continue
            key = (url, prompt_id_value, model_id)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or key in seen:
                continue
            seen.add(key)
            rows.append([url, proj_name, prompt_text, model_name, run_date.isoformat()])
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["URL", "Project", "Prompt", "Model", "Run date"])
    writer.writerows(rows)
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=references.csv"},
    )


@router.patch("/prompts/{prompt_id}/active", response_model=AdminPromptRead)
async def set_prompt_active(
    prompt_id: int,
    is_active: bool,
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> AdminPromptRead:
    prompt = (await session.execute(
        select(Prompt)
        .options(selectinload(Prompt.models).selectinload(PromptModel.model), selectinload(Prompt.project))
        .where(Prompt.id == prompt_id)
    )).scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرامپت یافت نشد")
    prompt.is_active = is_active
    await session.commit()
    await session.refresh(prompt)
    return _admin_prompt_read(prompt)

