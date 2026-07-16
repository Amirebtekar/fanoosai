from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_session
from app.auth.fastapi_users import fastapi_users
from app.database.models import Project, Prompt, AIModel, AIRun, Brand, RunBrand, UserTable
from app.analytics.schema import Page, LatestRun, BrandDetails

router = APIRouter(tags=["analytics"])

async def owner(project_id, session, user):
    if not await session.scalar(select(Project.id).where(Project.id == project_id, Project.user_id == user.id)):
        raise HTTPException(404, "پروژه یافت نشد")

async def owned_brand(brand_id: int, session: AsyncSession, user: UserTable) -> None:
    stmt = (
        select(Brand.id)
        .join(RunBrand)
        .join(AIRun)
        .join(Prompt)
        .join(Project)
        .where(Brand.id == brand_id, Project.user_id == user.id)
    )
    if not await session.scalar(stmt):
        raise HTTPException(404, "Brand not found")

@router.get("/projects/{project_id}/runs", response_model=Page)
async def runs(project_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    await owner(project_id, session, user)
    stmt = select(AIRun, Prompt, AIModel).join(Prompt).join(AIModel).where(Prompt.project_id == project_id)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(stmt.order_by(AIRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    items = [LatestRun(ai_run_id=r.id, prompt=p.text, ai_model=m.name, status=r.status, extraction_status=r.extraction_status, created_at=r.created_at, completed_at=r.completed_at) for r, p, m in rows]
    return Page(items=items, page=page, page_size=page_size, total=total)

@router.get("/brands/{brand_id}", response_model=BrandDetails)
async def details(brand_id: int, session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    await owned_brand(brand_id, session, user)
    stmt = select(Brand, func.count(RunBrand.id), func.avg(RunBrand.rank), func.min(RunBrand.rank), func.max(RunBrand.rank), func.min(RunBrand.created_at), func.max(RunBrand.created_at)).join(RunBrand).join(AIRun).join(Prompt).join(Project).where(Brand.id == brand_id, Project.user_id == user.id).group_by(Brand.id)
    row = (await session.execute(stmt)).one_or_none()
    if not row: raise HTTPException(404, "برند یافت نشد")
    b, count, avg, best, worst, first, last = row
    return BrandDetails(brand_id=b.id, name=b.name, domain=b.domain, observation_count=count, average_rank=avg, best_rank=best, worst_rank=worst, first_observed=first, last_observed=last)
