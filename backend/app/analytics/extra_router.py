from datetime import datetime, timedelta, timezone
import csv, io, secrets
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_session
from app.auth.fastapi_users import fastapi_users
from app.database.models import Prompt, AIModel, AIRun, ReportShare, UserTable
from app.repositories.project_repository import ProjectRepository
from app.analytics.schema import Page, LatestRun

router = APIRouter(tags=["analytics"])

async def reader(project_id, session, user):
    if not await ProjectRepository(session).can_read(project_id, user.id):
        raise HTTPException(404, "پروژه یافت نشد")


async def manager(project_id, session, user):
    if not await ProjectRepository(session).can_manage_project(project_id, user.id):
        raise HTTPException(403, "Project manager role required")

@router.get("/projects/{project_id}/runs", response_model=Page)
async def runs(project_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    await reader(project_id, session, user)
    stmt = select(AIRun, Prompt, AIModel).join(Prompt).join(AIModel).where(Prompt.project_id == project_id)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(stmt.order_by(AIRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    items = [LatestRun(ai_run_id=r.id, prompt=p.text, ai_model=m.name, status=r.status, extraction_status=r.extraction_status, created_at=r.created_at, completed_at=r.completed_at) for r, p, m in rows]
    return Page(items=items, page=page, page_size=page_size, total=total)

@router.get("/projects/{project_id}/runs.csv")
async def export_runs(project_id: int, session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    await reader(project_id, session, user)
    rows = (await session.execute(select(AIRun.id, AIModel.name, AIRun.status, AIRun.created_at).join(Prompt).join(AIModel).where(Prompt.project_id == project_id))).all()
    out = io.StringIO(); writer = csv.writer(out); writer.writerow(("run_id", "model", "status", "created_at")); writer.writerows(rows)
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=runs.csv"})

@router.post("/projects/{project_id}/shares")
async def create_share(project_id: int, session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    await manager(project_id, session, user)
    share = ReportShare(project_id=project_id, token=secrets.token_urlsafe(32), expires_at=datetime.now(timezone.utc) + timedelta(days=7)); session.add(share); await session.commit(); return {"token": share.token, "expires_at": share.expires_at}

@router.delete("/projects/{project_id}/shares/{token}", status_code=204)
async def revoke_share(project_id: int, token: str, session: AsyncSession = Depends(get_session), user: UserTable = Depends(fastapi_users.current_user())):
    await manager(project_id, session, user)
    share = await session.scalar(select(ReportShare).where(ReportShare.project_id == project_id, ReportShare.token == token, ReportShare.revoked_at.is_(None)))
    if not share: raise HTTPException(404, "Share not found")
    share.revoked_at = datetime.now(timezone.utc); await session.commit()

@router.get("/shared/{token}")
async def shared_report(token: str, session: AsyncSession = Depends(get_session)):
    share = await session.scalar(select(ReportShare).where(ReportShare.token == token, ReportShare.revoked_at.is_(None), ReportShare.expires_at > datetime.now(timezone.utc)))
    if not share: raise HTTPException(404, "Share not found")
    rows = (await session.execute(select(AIModel.name, AIRun.status, AIRun.created_at).join(Prompt).join(AIModel).where(Prompt.project_id == share.project_id).order_by(AIRun.created_at.desc()).limit(100))).all()
    return {"runs": [{"model": model, "status": status, "created_at": created_at} for model, status, created_at in rows]}
