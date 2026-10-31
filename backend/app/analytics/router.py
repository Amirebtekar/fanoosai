import json
import math
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_session
from app.core.config import settings
from app.auth.fastapi_users import fastapi_users
from app.database.models import Project, Prompt, PromptModel, AIModel, AIRun, Brand, RunBrand, ProjectBrand, OrganizationMember, UserTable
from app.analytics.schema import *
from app.analytics.search_metadata import group_search_queries, group_searched_sites
from app.services.brand_persistence_service import normalize_brand_name

router = APIRouter(tags=["analytics"])

async def owned_project(project_id: int, session: AsyncSession, user: UserTable):
    if not await session.scalar(select(Project.id).join(OrganizationMember, OrganizationMember.organization_id == Project.organization_id).where(Project.id == project_id, OrganizationMember.user_id == user.id)):
        raise HTTPException(404, "پروژه یافت نشد")

def as_tehran(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=ZoneInfo(settings.RUN_TIMEZONE))


def filters(stmt, project_id, prompt_id=None, ai_model_id=None, start=None, end=None):
    start, end = as_tehran(start), as_tehran(end)
    stmt = stmt.where(Prompt.project_id == project_id)
    if prompt_id is not None: stmt = stmt.where(AIRun.prompt_id == prompt_id)
    if ai_model_id is not None: stmt = stmt.where(AIRun.ai_model_id == ai_model_id)
    if start is not None: stmt = stmt.where(AIRun.created_at >= start)
    if end is not None: stmt = stmt.where(AIRun.created_at <= end)
    return stmt


def visibility_percent(owned_runs: int, successful_runs: int) -> float:
    return round(owned_runs / successful_runs * 100, 1) if successful_runs else 0.0

RANK_REPORT_MAX_DAYS = 62
RANK_REPORT_TIMEZONE = ZoneInfo(settings.RUN_TIMEZONE)

def build_rank_report_rows(rows, days: list[str]) -> list[RankReportRow]:
    grouped: dict[tuple[int, int], dict] = {}
    for prompt_id, prompt, ai_model_id, ai_model, day, avg_rank, count in rows:
        entry = grouped.setdefault((prompt_id, ai_model_id), {
            "prompt_id": prompt_id,
            "prompt": prompt,
            "ai_model_id": ai_model_id,
            "ai_model": ai_model,
            "daily": {},
            "weighted": 0.0,
            "count": 0,
        })
        day_key = day.isoformat() if hasattr(day, "isoformat") else str(day)
        value = float(avg_rank)
        entry["daily"][day_key] = round(value, 2)
        entry["weighted"] += value * int(count)
        entry["count"] += int(count)

    items = []
    for entry in grouped.values():
        observed = [day for day in days if day in entry["daily"]]
        first, last = (entry["daily"][observed[0]], entry["daily"][observed[-1]]) if len(observed) > 1 else (None, None)
        items.append(RankReportRow(
            prompt_id=entry["prompt_id"],
            prompt=entry["prompt"],
            ai_model_id=entry["ai_model_id"],
            ai_model=entry["ai_model"],
            appearances=entry["count"],
            average_rank=round(entry["weighted"] / entry["count"], 2) if entry["count"] else None,
            rank_change=round(last - first, 2) if first is not None else None,
            daily=entry["daily"],
        ))
    return sorted(items, key=lambda item: (item.prompt, item.ai_model))

async def owned_prompt(prompt_id: int, session: AsyncSession, user: UserTable) -> Prompt:
    prompt = await session.scalar(
        select(Prompt).join(Project).join(OrganizationMember, OrganizationMember.organization_id == Project.organization_id).where(Prompt.id == prompt_id, OrganizationMember.user_id == user.id)
    )
    if not prompt:
        raise HTTPException(404, "Prompt not found")
    return prompt

@router.get("/projects/{project_id}/dashboard", response_model=DashboardSummary)
async def dashboard(project_id: int, session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    await owned_project(project_id, session, user)
    base = select(AIRun).join(Prompt)
    total = await session.scalar(select(func.count(AIRun.id)).select_from(AIRun).join(Prompt).where(Prompt.project_id == project_id)) or 0
    values = await session.execute(select(
        select(func.count(Prompt.id)).where(Prompt.project_id == project_id).scalar_subquery(),
        select(func.count(distinct(PromptModel.ai_model_id))).join(Prompt, Prompt.id == PromptModel.prompt_id).where(Prompt.project_id == project_id, PromptModel.ai_model_id.in_(select(AIModel.id).where(AIModel.is_active))).scalar_subquery(),
        select(func.count(distinct(RunBrand.brand_id))).join(AIRun).join(Prompt).where(Prompt.project_id == project_id).scalar_subquery(),
        select(func.count(AIRun.id)).join(Prompt).where(Prompt.project_id == project_id, AIRun.status == "success").scalar_subquery(),
        select(func.count(AIRun.id)).join(Prompt).where(Prompt.project_id == project_id, AIRun.status != "success").scalar_subquery(),
        select(func.max(AIRun.completed_at)).join(Prompt).where(Prompt.project_id == project_id, AIRun.status == "success").scalar_subquery(),
    ))
    p, m, b, success, failed, latest = values.one()
    brand_match = or_(
        ProjectBrand.brand_id == Brand.id,
        func.lower(ProjectBrand.domain) == func.lower(Brand.domain),
        func.lower(ProjectBrand.name) == func.lower(Brand.name),
    )
    configured = (await session.execute(
        select(ProjectBrand.name, ProjectBrand.kind, func.count(RunBrand.id), func.avg(RunBrand.rank))
        .outerjoin(Brand, brand_match)
        .outerjoin(RunBrand, RunBrand.brand_id == Brand.id)
        .outerjoin(AIRun, AIRun.id == RunBrand.ai_run_id)
        .outerjoin(Prompt, Prompt.id == AIRun.prompt_id)
        .where(ProjectBrand.project_id == project_id, Prompt.project_id == project_id)
        .group_by(ProjectBrand.name, ProjectBrand.kind)
    )).all()
    owned_runs = await session.scalar(
        select(func.count(distinct(RunBrand.ai_run_id)))
        .select_from(ProjectBrand)
        .join(Brand, brand_match)
        .join(RunBrand, RunBrand.brand_id == Brand.id)
        .join(AIRun, AIRun.id == RunBrand.ai_run_id)
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .where(
            ProjectBrand.project_id == project_id,
            ProjectBrand.kind == "owned",
            Prompt.project_id == project_id,
            AIRun.status == "success",
        )
    ) or 0
    owned = [(count, avg) for _, kind, count, avg in configured if kind == "owned"]
    appearances = sum(count for count, _ in owned)
    average_rank = sum(float(avg) * count for count, avg in owned if avg is not None) / appearances if appearances else None
    competitors = [{"name": name, "appearances": count, "average_rank": float(avg) if avg is not None else None} for name, kind, count, avg in configured if kind == "competitor"]
    return DashboardSummary(prompt_count=p, active_model_count=m, run_count=total, brand_count=b, last_successful_run=latest, successful_run_count=success, failed_run_count=failed, visibility=visibility_percent(owned_runs, success), average_rank=average_rank, appearances=appearances, competitors=competitors)

def model_performance_window(days: int, now: datetime | None = None) -> tuple[datetime, datetime]:
    if days not in {7, 30}:
        raise ValueError("days must be 7 or 30")
    timezone = ZoneInfo(settings.RUN_TIMEZONE)
    current = now or datetime.now(timezone)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone)
    today = current.astimezone(timezone).date()
    start = datetime.combine(today - timedelta(days=days - 1), time.min, tzinfo=timezone)
    end = datetime.combine(today + timedelta(days=1), time.min, tzinfo=timezone)
    return start.astimezone(dt_timezone.utc), end.astimezone(dt_timezone.utc)


@router.get("/projects/{project_id}/model-performance", response_model=list[ModelPerformance])
async def model_performance(
    project_id: int,
    days: int = Query(7),
    session: AsyncSession = Depends(get_session),
    user: UserTable = Depends(fastapi_users.current_user()),
):
    await owned_project(project_id, session, user)
    try:
        start, end = model_performance_window(days)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    rows = await session.execute(
        select(
            AIModel.name,
            func.count(AIRun.id),
            func.count(AIRun.id).filter(AIRun.status == "success"),
            func.count(AIRun.id).filter(AIRun.status == "success", AIRun.provider_used.in_(["avalai", "9router"])),
            func.count(AIRun.id).filter(AIRun.status != "success"),
        )
        .join(PromptModel, PromptModel.ai_model_id == AIModel.id)
        .join(Prompt, Prompt.id == PromptModel.prompt_id)
        .outerjoin(AIRun, and_(
            AIRun.prompt_id == Prompt.id,
            AIRun.ai_model_id == AIModel.id,
            AIRun.created_at >= start,
            AIRun.created_at < end,
        ))
        .where(Prompt.project_id == project_id)
        .group_by(AIModel.id, AIModel.name)
        .order_by(AIModel.name)
    )
    return [
        ModelPerformance(
            ai_model=name,
            total_runs=total_runs,
            successful_runs=successful_runs,
            direct_successful_runs=direct_successful_runs,
            failed_runs=failed_runs,
            success_rate=round(successful_runs / total_runs * 100, 1) if total_runs else 0,
        )
        for name, total_runs, successful_runs, direct_successful_runs, failed_runs in rows.all()
    ]

@router.get("/projects/{project_id}/brand-rank-summary", response_model=Page)
async def brand_rank_summary(
    project_id: int,
    days: int = Query(7),
    prompt_id: int | None = Query(None, gt=0),
    brand_id: int | None = Query(None, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: UserTable = Depends(fastapi_users.current_user()),
):
    await owned_project(project_id, session, user)
    try:
        start, end = model_performance_window(days)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    stmt = (
        select(
            Prompt.id.label("prompt_id"),
            Prompt.text.label("prompt"),
            Brand.id.label("brand_id"),
            Brand.name.label("brand"),
            Brand.domain.label("domain"),
            func.avg(RunBrand.rank).label("average_rank"),
            func.count(RunBrand.id).label("observations"),
        )
        .select_from(RunBrand)
        .join(AIRun, AIRun.id == RunBrand.ai_run_id)
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .join(Brand, Brand.id == RunBrand.brand_id)
        .where(
            Prompt.project_id == project_id,
            AIRun.status == "success",
            AIRun.created_at >= start,
            AIRun.created_at < end,
        )
        .group_by(Prompt.id, Prompt.text, Brand.id, Brand.name, Brand.domain)
    )
    if prompt_id is not None:
        stmt = stmt.where(Prompt.id == prompt_id)
    if brand_id is not None:
        stmt = stmt.where(Brand.id == brand_id)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(
        stmt.order_by(func.avg(RunBrand.rank), Brand.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).all()
    # Denominator for "observations": every successful answer of the prompt in the
    # same window, so "34 of 35" means the brand was missing from one answer.
    prompt_ids = sorted({row[0] for row in rows})
    totals: dict[int, int] = {}
    if prompt_ids:
        totals = dict((await session.execute(
            select(AIRun.prompt_id, func.count(AIRun.id))
            .where(
                AIRun.prompt_id.in_(prompt_ids),
                AIRun.status == "success",
                AIRun.created_at >= start,
                AIRun.created_at < end,
            )
            .group_by(AIRun.prompt_id)
        )).all())
    items = [BrandRankSummaryItem(
        prompt_id=prompt_value,
        prompt=prompt_text,
        brand_id=brand_value,
        brand=brand,
        domain=domain,
        average_rank=float(average_rank),
        observations=observations,
        total_runs=max(int(totals.get(prompt_value, 0)), observations),
    ) for prompt_value, prompt_text, brand_value, brand, domain, average_rank, observations in rows]
    return Page(items=items, page=page, page_size=page_size, total=total)


RADAR_STRENGTH_WEIGHTS = {
    "visibility": 0.35,
    "rank_score": 0.25,
    "top_three": 0.15,
    "model_coverage": 0.15,
    "prompt_coverage": 0.10,
}
RADAR_MIN_SAMPLE = 5
RADAR_MIN_SAMPLE_SHARE = 0.05


def normalize_domain(domain: str | None) -> str:
    return (domain or "").strip().casefold().rstrip(".")


def is_owned_brand(brand_id: int, domain: str | None, owned_brand_ids: set[int], owned_domains: set[str]) -> bool:
    return brand_id in owned_brand_ids or normalize_domain(domain) in owned_domains


async def owned_brand_keys(project_id: int, session: AsyncSession) -> tuple[set[int], set[str]]:
    owned = (await session.execute(
        select(ProjectBrand.brand_id, ProjectBrand.domain)
        .where(ProjectBrand.project_id == project_id, ProjectBrand.kind == "owned")
    )).all()
    owned_brand_ids = {brand_id for brand_id, _ in owned if brand_id is not None}
    owned_domains = {normalize_domain(domain) for _, domain in owned if normalize_domain(domain)}
    return owned_brand_ids, owned_domains


def window_run_filter(project_id: int, start: datetime, end: datetime, prompt_id: int | None = None) -> list:
    run_filter = [
        Prompt.project_id == project_id,
        AIRun.status == "success",
        AIRun.created_at >= start,
        AIRun.created_at < end,
    ]
    if prompt_id is not None:
        run_filter.append(Prompt.id == prompt_id)
    return run_filter


def rank_score(average_rank: float | None) -> float:
    """Map an average rank to 0..100 (rank 1 -> 100, rank 10 or worse -> 0)."""
    if average_rank is None:
        return 0.0
    return round(max(0.0, min(100.0, (10.0 - float(average_rank)) / 9.0 * 100.0)), 1)


def build_competitor_radar(
    rows,
    *,
    total_runs: int,
    total_models: int,
    total_prompts: int,
    owned_domains: set[str],
    owned_brand_ids: set[int],
    limit: int,
    days: int,
) -> CompetitorRadar:
    def pct(value: int, total: int) -> float:
        return round(min(100.0, value / total * 100.0), 1) if total else 0.0

    min_sample = max(RADAR_MIN_SAMPLE, total_runs * RADAR_MIN_SAMPLE_SHARE)

    brands = []
    for brand_id, name, domain, appearances, avg_rank, top_three_count, models, prompts in rows:
        appearances = int(appearances or 0)
        average = float(avg_rank) if avg_rank is not None else None
        confidence = min(1.0, appearances / min_sample) if min_sample else 0.0
        axes = {
            "visibility": pct(appearances, total_runs),
            "rank_score": round(rank_score(average) * confidence, 1),
            "top_three": pct(int(top_three_count or 0), appearances),
            "model_coverage": pct(int(models or 0), total_models),
            "prompt_coverage": pct(int(prompts or 0), total_prompts),
        }
        strength = round(sum(axes[key] * weight for key, weight in RADAR_STRENGTH_WEIGHTS.items()), 1)
        is_owned = is_owned_brand(brand_id, domain, owned_brand_ids, owned_domains)
        brands.append(CompetitorRadarBrand(
            brand_id=brand_id, brand=name, domain=domain, is_owned=is_owned, strength=strength, **axes,
            appearances=appearances, average_rank=round(average, 2) if average is not None else None,
            top_three_count=int(top_three_count or 0), models=int(models or 0), prompts=int(prompts or 0),
        ))
    brands.sort(key=lambda item: (-item.strength, -item.appearances, item.brand))
    owned = [item for item in brands if item.is_owned]
    top = [item for item in brands if not item.is_owned][: max(limit - len(owned[:1]), 0)]
    selected = sorted(owned[:1] + top, key=lambda item: (-item.strength, -item.appearances, item.brand))
    return CompetitorRadar(days=days, total_runs=total_runs, total_models=total_models, total_prompts=total_prompts, brands=selected)


@router.get("/projects/{project_id}/competitor-radar", response_model=CompetitorRadar)
async def competitor_radar(
    project_id: int,
    days: int = Query(30),
    prompt_id: int | None = Query(None, gt=0),
    limit: int = Query(6, ge=2, le=10),
    session: AsyncSession = Depends(get_session),
    user: UserTable = Depends(fastapi_users.current_user()),
):
    """Strongest brands of a project (always including the project's own brand) on five axes."""
    await owned_project(project_id, session, user)
    try:
        start, end = model_performance_window(days)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    run_filter = window_run_filter(project_id, start, end, prompt_id)

    total_runs, total_models, total_prompts = (await session.execute(
        select(
            func.count(AIRun.id), func.count(distinct(AIRun.ai_model_id)), func.count(distinct(AIRun.prompt_id)),
        )
        .select_from(AIRun).join(Prompt, Prompt.id == AIRun.prompt_id)
        .where(*run_filter)
    )).one()

    rows = (await session.execute(
        select(
            Brand.id, Brand.name, Brand.domain,
            func.count(distinct(RunBrand.ai_run_id)),
            func.avg(RunBrand.rank),
            func.count(distinct(RunBrand.ai_run_id)).filter(RunBrand.rank <= 3),
            func.count(distinct(AIRun.ai_model_id)),
            func.count(distinct(AIRun.prompt_id)),
        )
        .select_from(RunBrand)
        .join(AIRun, AIRun.id == RunBrand.ai_run_id)
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .join(Brand, Brand.id == RunBrand.brand_id)
        .where(*run_filter)
        .group_by(Brand.id, Brand.name, Brand.domain)
    )).all()

    owned_brand_ids, owned_domains = await owned_brand_keys(project_id, session)

    return build_competitor_radar(
        rows,
        total_runs=int(total_runs or 0), total_models=int(total_models or 0), total_prompts=int(total_prompts or 0),
        owned_domains=owned_domains, owned_brand_ids=owned_brand_ids, limit=limit, days=days,
    )


PROMPT_LEADER_MIN_APPEARANCES = 2
PROMPT_LEADER_MIN_SHARE = 0.2


def prompt_leader_threshold(total_runs: int) -> int:
    return max(PROMPT_LEADER_MIN_APPEARANCES, math.ceil(total_runs * PROMPT_LEADER_MIN_SHARE))


def build_prompt_leaders(rows, totals: dict[int, int], owned_brand_ids: set[int], owned_domains: set[str]) -> list[PromptLeaderItem]:
    """rows: (prompt_id, prompt, brand_id, brand, domain, appearances, average_rank)."""
    prompts: dict[int, dict] = {}
    for prompt_id, prompt, brand_id, brand, domain, appearances, average_rank in rows:
        if average_rank is None:
            continue
        entry = prompts.setdefault(prompt_id, {"prompt": prompt, "brands": []})
        entry["brands"].append(PromptLeaderBrand(
            brand_id=brand_id, brand=brand, domain=domain,
            average_rank=round(float(average_rank), 2), appearances=int(appearances or 0),
        ))

    items = []
    for prompt_id, entry in prompts.items():
        brands = entry["brands"]
        total_runs = max([int(totals.get(prompt_id, 0) or 0), *(brand.appearances for brand in brands)])
        threshold = prompt_leader_threshold(total_runs)
        eligible = [brand for brand in brands if brand.appearances >= threshold] or brands
        eligible.sort(key=lambda brand: (brand.average_rank, -brand.appearances, brand.brand))
        leader = eligible[0]
        positions = {brand.brand_id: index + 1 for index, brand in enumerate(eligible)}
        owned = sorted(
            (brand for brand in brands if is_owned_brand(brand.brand_id, brand.domain, owned_brand_ids, owned_domains)),
            key=lambda brand: (positions.get(brand.brand_id, math.inf), brand.average_rank, -brand.appearances),
        )
        own = None
        if owned:
            position = positions.get(owned[0].brand_id)
            own = PromptLeaderOwn(**owned[0].model_dump(), position=position, eligible=position is not None)
        items.append(PromptLeaderItem(
            prompt_id=prompt_id, prompt=entry["prompt"], total_runs=total_runs,
            leader=leader, own=own, own_is_leader=own is not None and own.brand_id == leader.brand_id,
        ))

    def sort_key(item: PromptLeaderItem):
        if item.own_is_leader:
            return (2, 0, 0.0, item.prompt)
        if item.own is None:
            return (0, 0, 0.0, item.prompt)
        position = item.own.position if item.own.position is not None else 10**6
        return (1, -position, -(item.own.average_rank - item.leader.average_rank), item.prompt)

    return sorted(items, key=sort_key)


@router.get("/projects/{project_id}/prompt-leaders", response_model=PromptLeaders)
async def prompt_leaders(
    project_id: int,
    days: int = Query(7),
    prompt_id: int | None = Query(None, gt=0),
    session: AsyncSession = Depends(get_session),
    user: UserTable = Depends(fastapi_users.current_user()),
):
    await owned_project(project_id, session, user)
    try:
        start, end = model_performance_window(days)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    run_filter = window_run_filter(project_id, start, end, prompt_id)
    totals = dict((await session.execute(
        select(AIRun.prompt_id, func.count(AIRun.id))
        .select_from(AIRun).join(Prompt, Prompt.id == AIRun.prompt_id)
        .where(*run_filter)
        .group_by(AIRun.prompt_id)
    )).all())
    rows = (await session.execute(
        select(
            Prompt.id, Prompt.text, Brand.id, Brand.name, Brand.domain,
            func.count(distinct(RunBrand.ai_run_id)),
            func.avg(RunBrand.rank),
        )
        .select_from(RunBrand)
        .join(AIRun, AIRun.id == RunBrand.ai_run_id)
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .join(Brand, Brand.id == RunBrand.brand_id)
        .where(*run_filter)
        .group_by(Prompt.id, Prompt.text, Brand.id, Brand.name, Brand.domain)
    )).all()
    owned_brand_ids, owned_domains = await owned_brand_keys(project_id, session)
    return PromptLeaders(
        days=days,
        has_own_brand=bool(owned_brand_ids or owned_domains),
        items=build_prompt_leaders(rows, totals, owned_brand_ids, owned_domains),
    )


@router.get("/projects/{project_id}/prompts", response_model=list[PromptAnalytics])
async def prompt_analytics(project_id: int, session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    await owned_project(project_id, session, user)
    latest_run = (
        select(
            AIRun.prompt_id,
            AIRun.status,
            func.row_number().over(
                partition_by=AIRun.prompt_id,
                order_by=(AIRun.created_at.desc(), AIRun.id.desc()),
            ).label("row_number"),
        )
        .subquery()
    )
    summary = (
        select(
            Prompt.id,
            Prompt.text,
            func.count(distinct(AIRun.id)).label("run_count"),
            func.max(AIRun.created_at).label("last_run"),
            func.count(distinct(RunBrand.brand_id)).label("brands_extracted"),
            latest_run.c.status.label("last_status"),
        )
        .outerjoin(AIRun, AIRun.prompt_id == Prompt.id)
        .outerjoin(RunBrand, RunBrand.ai_run_id == AIRun.id)
        .outerjoin(
            latest_run,
            (latest_run.c.prompt_id == Prompt.id) & (latest_run.c.row_number == 1),
        )
        .where(Prompt.project_id == project_id)
        .group_by(Prompt.id, Prompt.text, latest_run.c.status)
        .order_by(Prompt.id)
        .limit(settings.ANALYTICS_PROMPT_LIMIT)
    )
    model_rows = await session.execute(
        select(PromptModel.prompt_id, AIModel.name)
        .join(AIModel, AIModel.id == PromptModel.ai_model_id)
        .join(Prompt, Prompt.id == PromptModel.prompt_id)
        .where(Prompt.project_id == project_id)
        .order_by(PromptModel.prompt_id, AIModel.name)
    )
    models_by_prompt: dict[int, list[str]] = {}
    for prompt_id, model_name in model_rows:
        models_by_prompt.setdefault(prompt_id, []).append(model_name)

    result = []
    for prompt_id, text, run_count, last_run, brands_extracted, last_status in (await session.execute(summary)).all():
        result.append(PromptAnalytics(
            prompt_id=prompt_id,
            prompt=text,
            models=models_by_prompt.get(prompt_id, []),
            run_count=run_count,
            last_run=last_run,
            brands_extracted=brands_extracted,
            last_status=last_status,
        ))
    return result

@router.get("/brands/{brand_id}/history", response_model=Page)
async def brand_history(brand_id: int, project_id: int, prompt_id: int | None = None, ai_model_id: int | None = None,
                        start_date: datetime | None = None, end_date: datetime | None = None,
                        page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                        session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    await owned_project(project_id, session, user)
    stmt = select(RunBrand.created_at, RunBrand.rank, AIModel.name, Prompt.text, AIRun.id).join(AIRun).join(Prompt).join(AIModel).where(RunBrand.brand_id == brand_id)
    stmt = filters(stmt, project_id, prompt_id, ai_model_id, start_date, end_date)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(stmt.order_by(RunBrand.created_at).offset((page - 1) * page_size).limit(page_size))).all()
    items = [BrandHistoryItem(date=d, rank=r, ai_model=m, prompt=p, ai_run_id=run_id) for d, r, m, p, run_id in rows]
    return Page(items=items, page=page, page_size=page_size, total=total)

@router.get("/prompts/{prompt_id}/history", response_model=Page)
async def prompt_history(prompt_id: int, ai_model_id: int | None = None, start_date: datetime | None = None, end_date: datetime | None = None,
                         page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                         session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    prompt = await owned_prompt(prompt_id, session, user)
    if not prompt: raise HTTPException(404, "Prompt یافت نشد")
    stmt = select(
        AIRun.id, AIModel.name, AIRun.created_at, AIRun.request_text, AIRun.response_text, AIRun.status, AIRun.extraction_status, func.count(RunBrand.id),
        *HISTORY_METADATA_COLUMNS,
    ).join(AIModel).join(Prompt, Prompt.id == AIRun.prompt_id).outerjoin(RunBrand).where(AIRun.prompt_id == prompt_id)
    stmt = filters(stmt, project_id=prompt.project_id, prompt_id=prompt_id, ai_model_id=ai_model_id, start=start_date, end=end_date)
    rows = (await session.execute(stmt.group_by(AIRun.id, AIModel.name).order_by(AIRun.created_at.desc()).offset((page-1)*page_size).limit(page_size))).all()
    count_stmt = filters(
        select(func.count(AIRun.id)).join(Prompt),
        project_id=prompt.project_id,
        prompt_id=prompt_id,
        ai_model_id=ai_model_id,
        start=start_date,
        end=end_date,
    )
    total = await session.scalar(count_stmt) or 0
    items = [prompt_history_item(row) for row in rows]
    return Page(items=items, page=page, page_size=page_size, total=total)


HISTORY_METADATA_COLUMNS = (
    AIRun.prompt_tokens, AIRun.completion_tokens, AIRun.total_tokens, AIRun.reasoning_tokens, AIRun.cached_tokens,
    AIRun.cost_irt, AIRun.cost_usd, AIRun.web_search_count, AIRun.web_search_queries, AIRun.web_search_actions, AIRun.citations,
)
HISTORY_METADATA_FIELDS = tuple(column.key for column in HISTORY_METADATA_COLUMNS)


def _json_items(value, kind: type) -> list | None:
    if not isinstance(value, list):
        return None
    return [item for item in value if isinstance(item, kind)]


def prompt_history_item(row) -> PromptHistoryItem:
    run_id, model, run_date, request_text, response_text, status, extraction_status, brands_count, *metadata = row
    values = dict(zip(HISTORY_METADATA_FIELDS, metadata))
    values["web_search_queries"] = _json_items(values.get("web_search_queries"), str)
    values["web_search_actions"] = _json_items(values.get("web_search_actions"), dict)
    values["citations"] = _json_items(values.get("citations"), dict)
    return PromptHistoryItem(
        ai_run_id=run_id, ai_model=model, run_date=run_date, request_text=request_text, response_text=response_text,
        status=status, extraction_status=extraction_status, brands_count=brands_count, **values,
    )


@router.get("/projects/{project_id}/cost-summary", response_model=CostSummary)
async def cost_summary(
    project_id: int,
    days: int = Query(7),
    session: AsyncSession = Depends(get_session),
    user: UserTable = Depends(fastapi_users.current_user()),
):
    await owned_project(project_id, session, user)
    try:
        start, end = model_performance_window(days)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    rows = (await session.execute(
        select(
            AIModel.name,
            func.count(AIRun.id),
            func.count(AIRun.id).filter(AIRun.cost_irt.isnot(None)),
            func.coalesce(func.sum(AIRun.cost_irt), 0),
            func.coalesce(func.sum(AIRun.cost_usd), 0),
            func.coalesce(func.sum(AIRun.total_tokens), 0),
            func.coalesce(func.sum(AIRun.web_search_count), 0),
        )
        .select_from(AIRun)
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .join(AIModel, AIModel.id == AIRun.ai_model_id)
        .where(
            Prompt.project_id == project_id,
            AIRun.status == "success",
            AIRun.created_at >= start,
            AIRun.created_at < end,
        )
        .group_by(AIModel.id, AIModel.name)
    )).all()
    return build_cost_summary(rows, days)


def build_cost_summary(rows, days: int) -> CostSummary:
    models = []
    totals = {"runs": 0, "with_cost": 0, "irt": 0.0, "usd": 0.0, "tokens": 0, "searches": 0}
    for name, runs, with_cost, cost_irt, cost_usd, tokens, searches in rows:
        runs, with_cost, tokens, searches = int(runs or 0), int(with_cost or 0), int(tokens or 0), int(searches or 0)
        cost_irt, cost_usd = float(cost_irt or 0), float(cost_usd or 0)
        totals["runs"] += runs
        totals["with_cost"] += with_cost
        totals["irt"] += cost_irt
        totals["usd"] += cost_usd
        totals["tokens"] += tokens
        totals["searches"] += searches
        models.append(CostSummaryModel(ai_model=name, runs=runs, cost_irt=round(cost_irt, 2), total_tokens=tokens, web_search_count=searches))
    models.sort(key=lambda item: (-item.cost_irt, -item.runs, item.ai_model))
    return CostSummary(
        days=days,
        total_cost_irt=round(totals["irt"], 2),
        total_cost_usd=round(totals["usd"], 6),
        runs_with_cost=totals["with_cost"],
        total_runs=totals["runs"],
        total_tokens=totals["tokens"],
        web_search_count=totals["searches"],
        models=models,
    )

@router.get("/projects/{project_id}/references", response_model=ProjectReferencesPage)
async def project_references(
    project_id: int,
    prompt_id: int | None = Query(None, gt=0),
    ai_model_id: int | None = Query(None, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: UserTable = Depends(fastapi_users.current_user()),
):
    await owned_project(project_id, session, user)
    stmt = (
        select(Prompt.id, Prompt.text, AIModel.id, AIModel.name, AIRun.created_at, AIRun.response_text)
        .select_from(AIRun)
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .join(AIModel, AIModel.id == AIRun.ai_model_id)
        .where(Prompt.project_id == project_id, AIRun.status == "success", AIRun.response_text.is_not(None))
        .order_by(AIRun.created_at.desc(), AIRun.id.desc())
    )
    if prompt_id is not None:
        stmt = stmt.where(AIRun.prompt_id == prompt_id)
    if ai_model_id is not None:
        stmt = stmt.where(AIRun.ai_model_id == ai_model_id)

    # ponytail: sources live in response JSON; normalize into a table if this scan becomes slow.
    items = []
    seen = set()
    for prompt_id_value, prompt_text, model_id, model_name, run_date, response_text in (await session.execute(stmt)).all():
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
            seen.add(key)
            items.append(ProjectReferenceItem(
                url=url,
                prompt_id=prompt_id_value,
                prompt=prompt_text,
                ai_model_id=model_id,
                ai_model=model_name,
                run_date=run_date,
            ))

    start = (page - 1) * page_size
    return ProjectReferencesPage(
        items=items[start:start + page_size],
        page=page,
        page_size=page_size,
        total=len(items),
    )

def _project_search_stmt(project_id: int, prompt_id: int | None, ai_model_id: int | None, *columns, condition):
    stmt = (
        select(Prompt.id, Prompt.text, AIModel.id, AIModel.name, AIRun.created_at, *columns)
        .select_from(AIRun)
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .join(AIModel, AIModel.id == AIRun.ai_model_id)
        .where(Prompt.project_id == project_id, AIRun.status == "success", condition)
        .order_by(AIRun.created_at.desc(), AIRun.id.desc())
    )
    if prompt_id is not None:
        stmt = stmt.where(AIRun.prompt_id == prompt_id)
    if ai_model_id is not None:
        stmt = stmt.where(AIRun.ai_model_id == ai_model_id)
    return stmt


@router.get("/projects/{project_id}/search-queries", response_model=ProjectSearchQueriesPage)
async def project_search_queries(
    project_id: int,
    prompt_id: int | None = Query(None, gt=0),
    ai_model_id: int | None = Query(None, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: UserTable = Depends(fastapi_users.current_user()),
):
    await owned_project(project_id, session, user)
    stmt = _project_search_stmt(
        project_id, prompt_id, ai_model_id, AIRun.web_search_queries, AIRun.web_search_actions,
        condition=or_(AIRun.web_search_queries.is_not(None), AIRun.web_search_actions.is_not(None)),
    )
    groups = group_search_queries((await session.execute(stmt)).all())
    start = (page - 1) * page_size
    return ProjectSearchQueriesPage(
        items=[ProjectSearchQueryItem(**{key: value for key, value in group.items() if key != "extra"}) for group in groups[start:start + page_size]],
        page=page,
        page_size=page_size,
        total=len(groups),
    )


@router.get("/projects/{project_id}/searched-sites", response_model=ProjectSearchedSitesPage)
async def project_searched_sites(
    project_id: int,
    prompt_id: int | None = Query(None, gt=0),
    ai_model_id: int | None = Query(None, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: UserTable = Depends(fastapi_users.current_user()),
):
    await owned_project(project_id, session, user)
    stmt = _project_search_stmt(
        project_id, prompt_id, ai_model_id, AIRun.web_search_actions,
        condition=AIRun.web_search_actions.is_not(None),
    )
    groups = group_searched_sites((await session.execute(stmt)).all())
    start = (page - 1) * page_size
    return ProjectSearchedSitesPage(
        items=[ProjectSearchedSiteItem(**{key: value for key, value in group.items() if key != "extra"}) for group in groups[start:start + page_size]],
        page=page,
        page_size=page_size,
        total=len(groups),
    )

@router.get("/projects/{project_id}/history", response_model=ProjectHistory)
async def project_history(project_id: int, prompt_id: int | None = None, ai_model_id: int | None = None,
                          start_date: datetime | None = None, end_date: datetime | None = None,
                          session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    await owned_project(project_id, session, user)
    base = filters(select(AIRun).join(Prompt), project_id, prompt_id, ai_model_id, start_date, end_date)
    total = await session.scalar(select(func.count()).select_from(base.subquery())) or 0
    success = await session.scalar(select(func.count()).select_from(base.where(AIRun.status == "success").subquery())) or 0
    brands = await session.scalar(select(func.count(distinct(RunBrand.brand_id))).join(AIRun).join(Prompt).where(Prompt.project_id == project_id)) or 0
    latest = await session.scalar(select(func.max(AIRun.completed_at)).select_from(base.where(AIRun.status == "success").subquery()))
    return ProjectHistory(total_runs=total, successful_runs=success, failed_runs=total-success, brands_count=brands, last_successful_run=latest)

@router.get("/prompts/{prompt_id}/latest-rankings", response_model=Page)
async def latest_rankings(prompt_id: int, ai_model_id: int | None = None, brand_id: int | None = None, start_date: datetime | None = None, end_date: datetime | None = None, sort: str = Query("rank", pattern="^(rank|date)$"),
                          page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                          session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    prompt = await owned_prompt(prompt_id, session, user)
    if not prompt: raise HTTPException(404, "Prompt یافت نشد")
    start_date, end_date = as_tehran(start_date), as_tehran(end_date)
    ranked = select(
        Brand.name.label("brand"),
        Brand.domain,
        RunBrand.rank,
        RunBrand.confidence,
        AIModel.name.label("ai_model"),
        AIRun.created_at.label("run_date"),
        func.row_number().over(
            partition_by=(RunBrand.brand_id, AIRun.ai_model_id),
            order_by=(AIRun.created_at.desc(), AIRun.id.desc()),
        ).label("row_number"),
    ).join(AIRun, AIRun.id == RunBrand.ai_run_id).join(Brand, Brand.id == RunBrand.brand_id).join(AIModel, AIModel.id == AIRun.ai_model_id).where(AIRun.prompt_id == prompt_id)
    if ai_model_id is not None:
        ranked = ranked.where(AIRun.ai_model_id == ai_model_id)
    if brand_id is not None:
        ranked = ranked.where(RunBrand.brand_id == brand_id)
    if start_date is not None:
        ranked = ranked.where(AIRun.created_at >= start_date)
    if end_date is not None:
        ranked = ranked.where(AIRun.created_at <= end_date)
    latest = ranked.subquery()
    total = await session.scalar(select(func.count()).select_from(latest).where(latest.c.row_number == 1)) or 0
    rows = (await session.execute(
        select(latest)
        .where(latest.c.row_number == 1)
        .order_by(latest.c.rank if sort == "rank" else latest.c.run_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).mappings().all()
    items = [LatestRanking(**{key: row[key] for key in ("brand", "domain", "rank", "confidence", "ai_model", "run_date")}) for row in rows]
    return Page(items=items, page=page, page_size=page_size, total=total)

@router.get("/brands/{brand_id}", response_model=BrandDetails)
async def brand_details(brand_id: int, session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    stmt = select(Brand, func.count(RunBrand.id), func.avg(RunBrand.rank), func.min(RunBrand.rank), func.max(RunBrand.rank), func.min(RunBrand.created_at), func.max(RunBrand.created_at)).join(RunBrand).join(AIRun).join(Prompt).join(Project).join(OrganizationMember, OrganizationMember.organization_id == Project.organization_id).where(Brand.id == brand_id, OrganizationMember.user_id == user.id).group_by(Brand.id)
    row = (await session.execute(stmt)).one_or_none()
    if not row: raise HTTPException(404, "برند یافت نشد")
    b, count, avg, best, worst, first, last = row
    return BrandDetails(brand_id=b.id, name=b.name, domain=b.domain, total_appearances=count, average_rank=avg, best_rank=best, worst_rank=worst, first_seen=first, last_seen=last)

@router.get("/prompts/{prompt_id}/rankings", response_model=list[PromptRankingItem])
async def prompt_rankings(prompt_id:int, session:AsyncSession=Depends(get_session), user:UserTable=Depends(fastapi_users.current_user())):
    await owned_prompt(prompt_id, session, user)
    ranked = select(
        Brand.name.label("brand"),
        Brand.domain,
        RunBrand.rank,
        AIModel.name.label("ai_model"),
        AIRun.created_at.label("date"),
        func.row_number().over(
            partition_by=(RunBrand.brand_id, AIRun.ai_model_id),
            order_by=(AIRun.created_at.desc(), AIRun.id.desc()),
        ).label("row_number"),
    ).join(AIRun, AIRun.id == RunBrand.ai_run_id).join(Brand, Brand.id == RunBrand.brand_id).join(AIModel, AIModel.id == AIRun.ai_model_id).where(AIRun.prompt_id == prompt_id).subquery()
    rows = (await session.execute(
        select(ranked)
        .where(ranked.c.row_number == 1)
        .order_by(ranked.c.date.desc())
        .limit(500)
    )).mappings().all()
    return [PromptRankingItem(brand=row["brand"], domain=row["domain"], rank=row["rank"], ai_model=row["ai_model"], date=row["date"]) for row in rows]

@router.get("/prompts/{prompt_id}/brand-trends", response_model=PromptBrandTrends)
async def prompt_brand_trends(
    prompt_id: int,
    ai_model_id: int | None = None,
    brand_ids: list[int] | None = Query(default=None, max_length=20),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    session: AsyncSession = Depends(get_session),
    user: UserTable = Depends(fastapi_users.current_user()),
):
    prompt = await owned_prompt(prompt_id, session, user)
    start_date, end_date = as_tehran(start_date), as_tehran(end_date)
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "start_date must be before end_date")

    stmt = (
        select(RunBrand, Brand, AIModel, AIRun)
        .join(Brand)
        .join(AIRun)
        .join(AIModel)
        .where(AIRun.prompt_id == prompt_id)
    )
    if ai_model_id is not None:
        stmt = stmt.where(AIRun.ai_model_id == ai_model_id)
    if brand_ids:
        stmt = stmt.where(RunBrand.brand_id.in_(brand_ids))
    if start_date is not None:
        stmt = stmt.where(AIRun.created_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(AIRun.created_at <= end_date)

    ranked = (
        select(
            RunBrand.brand_id.label("brand_id"),
            Brand.name.label("brand"),
            Brand.domain.label("domain"),
            AIModel.id.label("ai_model_id"),
            AIModel.name.label("ai_model"),
            RunBrand.rank.label("rank"),
            AIRun.id.label("ai_run_id"),
            AIRun.created_at.label("date"),
            func.row_number().over(
                partition_by=(RunBrand.brand_id, AIRun.ai_model_id),
                order_by=(AIRun.created_at.desc(), AIRun.id.desc()),
            ).label("point_rank"),
        )
        .select_from(RunBrand)
        .join(Brand)
        .join(AIRun)
        .join(AIModel)
        .where(AIRun.prompt_id == prompt_id)
    )
    if ai_model_id is not None:
        ranked = ranked.where(AIRun.ai_model_id == ai_model_id)
    if brand_ids:
        ranked = ranked.where(RunBrand.brand_id.in_(brand_ids))
    if start_date is not None:
        ranked = ranked.where(AIRun.created_at >= start_date)
    if end_date is not None:
        ranked = ranked.where(AIRun.created_at <= end_date)
    ranked = ranked.subquery()
    rows = (await session.execute(
        select(ranked)
        .where(ranked.c.point_rank <= settings.TREND_MAX_POINTS_PER_SERIES)
        .order_by(ranked.c.brand_id, ranked.c.ai_model_id, ranked.c.date.asc())
    )).mappings().all()
    grouped: dict[tuple[str, int], list[dict]] = {}
    for row in rows:
        grouped.setdefault((normalize_brand_name(row["brand"]), row["ai_model_id"]), []).append(row)

    items = []
    for observations in grouped.values():
        first = observations[0]
        last = observations[-1]
        rank_change = last["rank"] - first["rank"] if len(observations) > 1 else None
        trend = "flat"
        if rank_change is not None:
            trend = "up" if rank_change < 0 else "down" if rank_change > 0 else "flat"
        items.append(BrandTrend(
            brand_id=first["brand_id"],
            brand=first["brand"],
            domain=first["domain"],
            ai_model_id=first["ai_model_id"],
            ai_model=first["ai_model"],
            points=[BrandTrendPoint(date=row["date"], rank=row["rank"], ai_run_id=row["ai_run_id"]) for row in observations],
            rank_change=rank_change,
            trend=trend,
        ))
    return PromptBrandTrends(prompt_id=prompt.id, items=items)

@router.get("/projects/{project_id}/rank-report", response_model=RankReport)
async def rank_report(
    project_id: int,
    brand_id: int = Query(..., gt=0),
    start_date: date = Query(...),
    end_date: date = Query(...),
    session: AsyncSession = Depends(get_session),
    user: UserTable = Depends(fastapi_users.current_user()),
):
    await owned_project(project_id, session, user)
    if start_date > end_date:
        raise HTTPException(422, "start_date must be before end_date")
    if (end_date - start_date).days + 1 > RANK_REPORT_MAX_DAYS:
        raise HTTPException(422, f"date range is limited to {RANK_REPORT_MAX_DAYS} days")
    start_dt = datetime.combine(start_date, time.min, tzinfo=RANK_REPORT_TIMEZONE).astimezone(dt_timezone.utc)
    end_dt = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=RANK_REPORT_TIMEZONE).astimezone(dt_timezone.utc)
    run_day = func.cast(func.timezone(RANK_REPORT_TIMEZONE.key, AIRun.created_at), Date)
    stmt = (
        select(
            Prompt.id.label("prompt_id"),
            Prompt.text.label("prompt"),
            AIModel.id.label("ai_model_id"),
            AIModel.name.label("ai_model"),
            run_day.label("day"),
            func.avg(RunBrand.rank).label("avg_rank"),
            func.count(RunBrand.id).label("appearances"),
        )
        .select_from(RunBrand)
        .join(AIRun, AIRun.id == RunBrand.ai_run_id)
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .join(AIModel, AIModel.id == AIRun.ai_model_id)
        .where(
            RunBrand.brand_id == brand_id,
            Prompt.project_id == project_id,
            AIRun.created_at >= start_dt,
            AIRun.created_at < end_dt,
        )
        .group_by(Prompt.id, Prompt.text, AIModel.id, AIModel.name, run_day)
    )
    rows = (await session.execute(stmt)).all()
    days = [(start_date + timedelta(days=offset)).isoformat() for offset in range((end_date - start_date).days + 1)]
    return RankReport(
        brand_id=brand_id,
        start_date=start_date,
        end_date=end_date,
        days=days,
        items=build_rank_report_rows(rows, days),
    )
