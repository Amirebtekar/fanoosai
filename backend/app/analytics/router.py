from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_session
from app.core.config import settings
from app.auth.fastapi_users import fastapi_users
from app.database.models import Project, Prompt, PromptModel, AIModel, AIRun, Brand, RunBrand, UserTable
from app.analytics.schema import *

router = APIRouter(tags=["analytics"])

async def owned_project(project_id: int, session: AsyncSession, user: UserTable):
    if not await session.scalar(select(Project.id).where(Project.id == project_id, Project.user_id == user.id)):
        raise HTTPException(404, "پروژه یافت نشد")

def filters(stmt, project_id, prompt_id=None, ai_model_id=None, start=None, end=None):
    stmt = stmt.where(Prompt.project_id == project_id)
    if prompt_id is not None: stmt = stmt.where(AIRun.prompt_id == prompt_id)
    if ai_model_id is not None: stmt = stmt.where(AIRun.ai_model_id == ai_model_id)
    if start is not None: stmt = stmt.where(AIRun.created_at >= start)
    if end is not None: stmt = stmt.where(AIRun.created_at <= end)
    return stmt

async def owned_prompt(prompt_id: int, session: AsyncSession, user: UserTable) -> Prompt:
    prompt = await session.scalar(
        select(Prompt).join(Project).where(Prompt.id == prompt_id, Project.user_id == user.id)
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
    return DashboardSummary(prompt_count=p, active_model_count=m, run_count=total, brand_count=b, last_successful_run=latest, successful_run_count=success, failed_run_count=failed)

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
    stmt = select(AIRun.id, AIModel.name, AIRun.created_at, AIRun.status, AIRun.extraction_status, func.count(RunBrand.id)).join(AIModel).outerjoin(RunBrand).where(AIRun.prompt_id == prompt_id)
    stmt = filters(stmt, project_id=prompt.project_id, prompt_id=prompt_id, ai_model_id=ai_model_id, start=start_date, end=end_date)
    rows = (await session.execute(stmt.group_by(AIRun.id, AIModel.name).order_by(AIRun.created_at.desc()).offset((page-1)*page_size).limit(page_size))).all()
    total = await session.scalar(select(func.count()).select_from(AIRun).where(AIRun.prompt_id == prompt_id)) or 0
    items = [PromptHistoryItem(ai_run_id=i, ai_model=m, run_date=d, status=s, extraction_status=e, brands_count=c) for i,m,d,s,e,c in rows]
    return Page(items=items, page=page, page_size=page_size, total=total)

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
async def latest_rankings(prompt_id: int, ai_model_id: int | None = None, brand_id: int | None = None,
                          page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                          session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    prompt = await owned_prompt(prompt_id, session, user)
    if not prompt: raise HTTPException(404, "Prompt یافت نشد")
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
    latest = ranked.subquery()
    total = await session.scalar(select(func.count()).select_from(latest).where(latest.c.row_number == 1)) or 0
    rows = (await session.execute(
        select(latest)
        .where(latest.c.row_number == 1)
        .order_by(latest.c.run_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).mappings().all()
    items = [LatestRanking(**{key: row[key] for key in ("brand", "domain", "rank", "confidence", "ai_model", "run_date")}) for row in rows]
    return Page(items=items, page=page, page_size=page_size, total=total)

@router.get("/brands/{brand_id}", response_model=BrandDetails)
async def brand_details(brand_id: int, session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    stmt = select(Brand, func.count(RunBrand.id), func.avg(RunBrand.rank), func.min(RunBrand.rank), func.max(RunBrand.rank), func.min(RunBrand.created_at), func.max(RunBrand.created_at)).join(RunBrand).join(AIRun).join(Prompt).join(Project).where(Brand.id == brand_id, Project.user_id == user.id).group_by(Brand.id)
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
        .order_by(ranked.c.brand_id, ranked.c.ai_model_id, ranked.c.date.desc())
    )).mappings().all()
    grouped: dict[tuple[int, int], list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["brand_id"], row["ai_model_id"]), []).append(row)

    items = []
    for (brand_id, _), observations in grouped.items():
        first = observations[0]
        last = observations[-1]
        rank_change = last["rank"] - first["rank"] if len(observations) > 1 else None
        trend = "flat"
        if rank_change is not None:
            trend = "up" if rank_change < 0 else "down" if rank_change > 0 else "flat"
        items.append(BrandTrend(
            brand_id=brand_id,
            brand=first["brand"],
            domain=first["domain"],
            ai_model_id=first["ai_model_id"],
            ai_model=first["ai_model"],
            points=[BrandTrendPoint(date=row["date"], rank=row["rank"], ai_run_id=row["ai_run_id"]) for row in observations],
            rank_change=rank_change,
            trend=trend,
        ))
    return PromptBrandTrends(prompt_id=prompt.id, items=items)
