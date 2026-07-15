from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_session
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
    prompts = (await session.execute(select(Prompt).where(Prompt.project_id == project_id).order_by(Prompt.id))).scalars().all()
    result=[]
    for p in prompts:
        runs=(await session.execute(select(AIRun).where(AIRun.prompt_id==p.id).order_by(AIRun.created_at.desc()))).scalars().all()
        models=(await session.execute(select(AIModel.name).join(PromptModel).where(PromptModel.prompt_id==p.id))).scalars().all()
        brands=await session.scalar(select(func.count(distinct(RunBrand.brand_id))).join(AIRun).where(AIRun.prompt_id==p.id)) or 0
        result.append(PromptAnalytics(prompt_id=p.id,prompt=p.text,models=list(models),run_count=len(runs),last_run=runs[0].created_at if runs else None,brands_extracted=brands,last_status=runs[0].status if runs else None))
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
    prompt = await session.scalar(select(Prompt).join(Project).where(Prompt.id == prompt_id, Project.user_id == user.id))
    if not prompt: raise HTTPException(404, "Prompt یافت نشد")
    stmt = select(AIRun.id, AIModel.name, AIRun.created_at, AIRun.status, AIRun.extraction_status, func.count(RunBrand.id)).join(AIModel).outerjoin(RunBrand).where(AIRun.prompt_id == prompt_id)
    stmt = filters(stmt, prompt_id=prompt_id, ai_model_id=ai_model_id, start=start_date, end=end_date)
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
    prompt = await session.scalar(select(Prompt).join(Project).where(Prompt.id == prompt_id, Project.user_id == user.id))
    if not prompt: raise HTTPException(404, "Prompt یافت نشد")
    stmt = select(RunBrand, Brand, AIModel, AIRun).join(Brand).join(AIRun).join(AIModel).where(AIRun.prompt_id == prompt_id).order_by(AIRun.created_at.desc())
    if ai_model_id is not None: stmt = stmt.where(AIRun.ai_model_id == ai_model_id)
    if brand_id is not None: stmt = stmt.where(RunBrand.brand_id == brand_id)
    latest = {}
    for link, brand, model, run in (await session.execute(stmt)).all(): latest.setdefault((brand.id, model.id), (link, brand, model, run))
    values = list(latest.values())
    items = [LatestRanking(brand=b.name, domain=b.domain, rank=l.rank, confidence=l.confidence, ai_model=m.name, run_date=r.created_at) for l,b,m,r in values[(page-1)*page_size:page*page_size]]
    return Page(items=items, page=page, page_size=page_size, total=len(values))

@router.get("/brands/{brand_id}", response_model=BrandDetails)
async def brand_details(brand_id: int, session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    stmt = select(Brand, func.count(RunBrand.id), func.avg(RunBrand.rank), func.min(RunBrand.rank), func.max(RunBrand.rank), func.min(RunBrand.created_at), func.max(RunBrand.created_at)).join(RunBrand).join(AIRun).join(Prompt).join(Project).where(Brand.id == brand_id, Project.user_id == user.id).group_by(Brand.id)
    row = (await session.execute(stmt)).one_or_none()
    if not row: raise HTTPException(404, "برند یافت نشد")
    b, count, avg, best, worst, first, last = row
    return BrandDetails(brand_id=b.id, name=b.name, domain=b.domain, total_appearances=count, average_rank=avg, best_rank=best, worst_rank=worst, first_seen=first, last_seen=last)

@router.get("/prompts/{prompt_id}/rankings", response_model=list[PromptRankingItem])
async def prompt_rankings(prompt_id:int, session:AsyncSession=Depends(get_session), user:UserTable=Depends(fastapi_users.current_user())):
    stmt=select(RunBrand,Brand,AIModel,AIRun).join(Brand).join(AIRun).join(AIModel).where(AIRun.prompt_id==prompt_id).order_by(AIRun.created_at.desc())
    rows=(await session.execute(stmt)).all(); latest={}
    for link,brand,model,run in rows: latest.setdefault((run.ai_model_id,brand.id),(link,brand,model,run))
    return [PromptRankingItem(brand=b.name,domain=b.domain,rank=l.rank,ai_model=m.name,date=r.created_at) for l,b,m,r in latest.values()]
