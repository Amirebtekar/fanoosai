from typing import List
import csv
import io
import json
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.fastapi_users import fastapi_users
from app.core.config import settings
from app.database.models import AIModel, AIRun, Brand, BrandAlias, Project, ProjectBrand, Prompt, PromptModel, RunBrand, UserTable
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
from app.services.brand_persistence_service import acquire_brand_write_lock, normalize_brand_domain, normalize_brand_name
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/admin", tags=["admin"])

require_superuser = fastapi_users.current_user(active=True, superuser=True)


class AdminPromptRead(PromptRead):
    model_config = ConfigDict(from_attributes=True)

    project_name: str = ""


class AdminCostItem(BaseModel):
    id: int
    created_at: datetime
    model: str
    model_provider: str | None
    execution_provider: str | None
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


class AdminBrand(BaseModel):
    id: int
    name: str
    domain: str
    run_links: int
    project_links: int
    aliases: int


class BrandMergeRequest(BaseModel):
    canonical_id: int = Field(gt=0)
    source_ids: list[int] = Field(min_length=1, max_length=50)


class BrandMergePreview(BaseModel):
    canonical: AdminBrand
    sources: list[AdminBrand]
    conflicts: list[str]
    run_links_to_move: int
    project_links_to_repoint: int
    aliases_to_preserve: int
    duplicate_run_links_to_remove: int


class BrandMergeResult(BaseModel):
    canonical: AdminBrand
    merged_ids: list[int]
    moved_run_links: int
    repointed_project_links: int
    removed_duplicate_run_links: int
    preserved_aliases: int


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
        select(AIRun.id, AIRun.created_at, AIModel.name, AIModel.provider, AIRun.provider_used, AIRun.prompt_tokens, AIRun.completion_tokens, AIRun.total_tokens, AIRun.cost_irt, AIRun.status)
        .join(AIModel, AIModel.id == AIRun.ai_model_id)
        .order_by(AIRun.created_at.desc())
    )).all()
    return [AdminCostItem(id=row[0], created_at=row[1], model=row[2], model_provider=row[3], execution_provider="9router" if row[4] == "avalai" else row[4], prompt_tokens=row[5], completion_tokens=row[6], total_tokens=row[7], cost_irt=row[8], status=row[9]) for row in rows]


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


async def _admin_brand_reads(session: AsyncSession, brand_ids: list[int] | None = None) -> list[AdminBrand]:
    stmt = select(
        Brand,
        select(func.count(RunBrand.id)).where(RunBrand.brand_id == Brand.id).scalar_subquery(),
        select(func.count(ProjectBrand.id)).where(ProjectBrand.brand_id == Brand.id).scalar_subquery(),
        select(func.count(BrandAlias.id)).where(BrandAlias.brand_id == Brand.id).scalar_subquery(),
    ).order_by(Brand.name, Brand.id)
    if brand_ids is not None:
        stmt = stmt.where(Brand.id.in_(brand_ids))
    rows = (await session.execute(stmt)).all()
    return [AdminBrand(id=brand.id, name=brand.name, domain=brand.domain, run_links=run_links, project_links=project_links, aliases=aliases) for brand, run_links, project_links, aliases in rows]


async def _selected_brands(session: AsyncSession, body: BrandMergeRequest, lock: bool = False) -> tuple[Brand, list[Brand]]:
    if body.canonical_id in body.source_ids or len(set(body.source_ids)) != len(body.source_ids) or any(brand_id <= 0 for brand_id in body.source_ids):
        raise HTTPException(status_code=422, detail="برند اصلی و برندهای ادغامی باید متفاوت و یکتا باشند")
    ids = [body.canonical_id, *body.source_ids]
    stmt = select(Brand).where(Brand.id.in_(ids)).order_by(Brand.id)
    if lock:
        stmt = stmt.with_for_update()
    brands = (await session.execute(stmt)).scalars().all()
    by_id = {brand.id: brand for brand in brands}
    if len(by_id) != len(ids):
        raise HTTPException(status_code=404, detail="یک یا چند برند پیدا نشد")
    return by_id[body.canonical_id], [by_id[brand_id] for brand_id in body.source_ids]


async def _alias_merge_count(session: AsyncSession, canonical: Brand, sources: list[Brand]) -> int:
    ids = [canonical.id, *(brand.id for brand in sources)]
    aliases = (await session.execute(select(BrandAlias).where(BrandAlias.brand_id.in_(ids)))).scalars().all()
    existing_names = {alias.normalized_name for alias in aliases if alias.brand_id == canonical.id and alias.normalized_name}
    existing_domains = {alias.normalized_domain for alias in aliases if alias.brand_id == canonical.id and alias.normalized_domain}
    source_ids = {brand.id for brand in sources}
    source_names = {normalize_brand_name(brand.name) for brand in sources}
    source_names.update(alias.normalized_name for alias in aliases if alias.brand_id in source_ids and alias.normalized_name)
    source_domains = {normalize_brand_domain(brand.domain) for brand in sources}
    source_domains.update(alias.normalized_domain for alias in aliases if alias.brand_id in source_ids and alias.normalized_domain)
    names_to_add = {name for name in source_names if name != normalize_brand_name(canonical.name) and name not in existing_names}
    domains_to_add = {domain for domain in source_domains if domain != normalize_brand_domain(canonical.domain) and domain not in existing_domains}
    return len(names_to_add) + len(domains_to_add)


def _ranked_run_brand_links(canonical_id: int, brand_ids: list[int]):
    return select(
        RunBrand.id.label("id"),
        func.row_number().over(
            partition_by=RunBrand.ai_run_id,
            order_by=(RunBrand.rank, case((RunBrand.brand_id == canonical_id, 0), else_=1), RunBrand.id),
        ).label("position"),
    ).where(RunBrand.brand_id.in_(brand_ids)).subquery()


def _brand_alias_conflicts(canonical: Brand, sources: list[Brand], outsider_brands: list[Brand], aliases: list[BrandAlias]) -> list[str]:
    involved_ids = {canonical.id, *(brand.id for brand in sources)}
    aliases_by_name = {alias.normalized_name: alias for alias in aliases if alias.normalized_name}
    aliases_by_domain = {alias.normalized_domain: alias for alias in aliases if alias.normalized_domain}
    conflicts = set()

    names = {brand.name for brand in sources}
    names.update(alias.name for alias in aliases if alias.brand_id in involved_ids and alias.name)
    canonical_name = normalize_brand_name(canonical.name)
    for name in names:
        normalized = normalize_brand_name(name)
        if not normalized or normalized == canonical_name:
            continue
        brand_conflict = any(normalize_brand_name(brand.name) == normalized for brand in outsider_brands)
        alias = aliases_by_name.get(normalized)
        if brand_conflict or (alias and alias.brand_id not in involved_ids):
            conflicts.add(f"نام «{name}» از قبل به برند دیگری متصل است")

    domains = {brand.domain for brand in sources}
    domains.update(alias.domain for alias in aliases if alias.brand_id in involved_ids and alias.domain)
    canonical_domain = normalize_brand_domain(canonical.domain)
    for domain in domains:
        normalized = normalize_brand_domain(domain)
        if not normalized or normalized == canonical_domain:
            continue
        brand_conflict = any(normalize_brand_domain(brand.domain) == normalized for brand in outsider_brands)
        alias = aliases_by_domain.get(normalized)
        if brand_conflict or (alias and alias.brand_id not in involved_ids):
            conflicts.add(f"دامنه «{domain}» از قبل به برند دیگری متصل است")
    return sorted(conflicts)


async def _brand_merge_counts(session: AsyncSession, canonical_id: int, source_ids: list[int]) -> tuple[int, int, int, int]:
    all_ids = [canonical_id, *source_ids]
    run_links = await session.scalar(select(func.count(RunBrand.id)).where(RunBrand.brand_id.in_(source_ids))) or 0
    project_links = await session.scalar(select(func.count(ProjectBrand.id)).where(ProjectBrand.brand_id.in_(source_ids))) or 0
    aliases = await session.scalar(select(func.count(BrandAlias.id)).where(BrandAlias.brand_id.in_(source_ids))) or 0
    per_run = (
        select(func.count(RunBrand.id).label("link_count"))
        .where(RunBrand.brand_id.in_(all_ids))
        .group_by(RunBrand.ai_run_id)
        .having(func.count(RunBrand.id) > 1)
    ).subquery()
    duplicates = await session.scalar(select(func.coalesce(func.sum(per_run.c.link_count - 1), 0))) or 0
    return int(run_links), int(project_links), int(aliases), int(duplicates)


@router.get("/brands", response_model=list[AdminBrand])
async def list_brands(
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> list[AdminBrand]:
    return await _admin_brand_reads(session)


@router.post("/brands/merge-preview", response_model=BrandMergePreview)
async def preview_brand_merge(
    body: BrandMergeRequest,
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> BrandMergePreview:
    canonical, sources = await _selected_brands(session, body)
    run_links, project_links, _, duplicates = await _brand_merge_counts(session, canonical.id, [brand.id for brand in sources])
    aliases = await _alias_merge_count(session, canonical, sources)
    brand_ids = [canonical.id, *(brand.id for brand in sources)]
    outsider_brands = (await session.execute(select(Brand).where(Brand.id.not_in(brand_ids)))).scalars().all()
    all_aliases = (await session.execute(select(BrandAlias))).scalars().all()
    conflicts = _brand_alias_conflicts(canonical, sources, outsider_brands, all_aliases)
    reads = {item.id: item for item in await _admin_brand_reads(session, brand_ids)}
    return BrandMergePreview(
        canonical=reads[canonical.id],
        sources=[reads[brand.id] for brand in sources],
        conflicts=conflicts,
        run_links_to_move=run_links,
        project_links_to_repoint=project_links,
        aliases_to_preserve=aliases,
        duplicate_run_links_to_remove=duplicates,
    )


@router.post("/brands/merge", response_model=BrandMergeResult)
async def merge_brands(
    body: BrandMergeRequest,
    session: AsyncSession = Depends(get_session),
    _: UserTable = Depends(require_superuser),
) -> BrandMergeResult:
    from sqlalchemy.exc import IntegrityError

    try:
        await acquire_brand_write_lock(session)
        canonical, sources = await _selected_brands(session, body, lock=True)
        source_ids = [brand.id for brand in sources]
        all_ids = [canonical.id, *source_ids]
        run_links, project_links, _, duplicates = await _brand_merge_counts(session, canonical.id, source_ids)

        outsider_brands = (await session.execute(select(Brand).where(Brand.id.not_in(all_ids)))).scalars().all()
        all_aliases = (await session.execute(select(BrandAlias))).scalars().all()
        alias_by_name = {alias.normalized_name: alias for alias in all_aliases if alias.normalized_name}
        alias_by_domain = {alias.normalized_domain: alias for alias in all_aliases if alias.normalized_domain}
        conflicts = _brand_alias_conflicts(canonical, sources, outsider_brands, all_aliases)
        if conflicts:
            raise HTTPException(status_code=409, detail="؛ ".join(conflicts))
        involved_aliases = [alias for alias in all_aliases if alias.brand_id in all_ids]
        source_candidates: list[tuple[str, str | None]] = [(brand.name, brand.domain) for brand in sources]
        source_candidates.extend((alias.name or "", alias.domain) for alias in involved_aliases if alias.brand_id in source_ids)

        for name, domain in source_candidates:
            normalized = normalize_brand_name(name) if name else ""
            if normalized and normalized != normalize_brand_name(canonical.name):
                conflicting_brand = next((brand for brand in outsider_brands if normalize_brand_name(brand.name) == normalized), None)
                alias = alias_by_name.get(normalized)
                if conflicting_brand or (alias and alias.brand_id not in all_ids):
                    raise HTTPException(status_code=409, detail=f"نام «{name}» به برند دیگری متصل است")
                if alias and alias.brand_id in source_ids:
                    alias.brand_id = canonical.id
                elif not alias:
                    created_alias = BrandAlias(brand_id=canonical.id, name=name, normalized_name=normalized)
                    session.add(created_alias)
                    alias_by_name[normalized] = created_alias
            normalized_domain = normalize_brand_domain(domain) if domain else ""
            if normalized_domain and normalized_domain != normalize_brand_domain(canonical.domain):
                conflicting_brand = next((brand for brand in outsider_brands if normalize_brand_domain(brand.domain) == normalized_domain), None)
                alias = alias_by_domain.get(normalized_domain)
                if conflicting_brand or (alias and alias.brand_id not in all_ids):
                    raise HTTPException(status_code=409, detail=f"دامنه «{domain}» به برند دیگری متصل است")
                if alias and alias.brand_id in source_ids:
                    alias.brand_id = canonical.id
                elif not alias:
                    created_alias = BrandAlias(brand_id=canonical.id, domain=domain, normalized_domain=normalized_domain)
                    session.add(created_alias)
                    alias_by_domain[normalized_domain] = created_alias

        ranked = _ranked_run_brand_links(canonical.id, all_ids)
        await session.execute(delete(RunBrand).where(RunBrand.id.in_(select(ranked.c.id).where(ranked.c.position > 1))))
        await session.execute(update(RunBrand).where(RunBrand.brand_id.in_(source_ids)).values(brand_id=canonical.id))
        await session.execute(update(ProjectBrand).where(ProjectBrand.brand_id.in_(source_ids)).values(brand_id=canonical.id))
        await session.execute(delete(Brand).where(Brand.id.in_(source_ids)))
        canonical_read = (await _admin_brand_reads(session, [canonical.id]))[0]
        preserved = await session.scalar(select(func.count(BrandAlias.id)).where(BrandAlias.brand_id == canonical.id)) or 0
        result = BrandMergeResult(
            canonical=canonical_read,
            merged_ids=source_ids,
            moved_run_links=run_links,
            repointed_project_links=project_links,
            removed_duplicate_run_links=duplicates,
            preserved_aliases=int(preserved),
        )
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="ادغام به‌دلیل تداخل داده انجام نشد؛ فهرست برندها را تازه کنید") from error
    except Exception:
        await session.rollback()
        raise

    return result

