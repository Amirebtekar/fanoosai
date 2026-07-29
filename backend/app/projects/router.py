from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import datetime, timezone

from app.dependencies import get_session
from app.database.models import UserTable, Project, ProjectBrand, Alert, AlertRule, AIRun, Brand, Prompt, RunBrand
from sqlalchemy import select
from app.repositories.project_repository import ProjectRepository
from app.repositories.user_repository import UserRepository
from app.services.project_service import ProjectService
from app.projects.schema import ProjectCreate, ProjectUpdate, ProjectRead, ProjectBrandCreate, ProjectBrandRead, ObservedBrandRead
from app.auth.fastapi_users import fastapi_users

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_to_dict(project: Project, prompt_count: int = 0, model_count: int = 0) -> dict:
    return {
        "id": project.id,
        "organization_id": project.organization_id,
        "name": project.name,
        "description": project.description,
        "website_url": project.website_url,
        "prompt_count": prompt_count,
        "model_count": model_count,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def get_project_service(
    session: AsyncSession = Depends(get_session)
) -> ProjectService:
    project_repo = ProjectRepository(session)
    user_repo = UserRepository(session)
    return ProjectService(project_repo, user_repo)

async def get_current_user(user: UserTable = Depends(fastapi_users.current_user())) -> UserTable:
    return user

@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
    current_user: UserTable = Depends(get_current_user),
) -> ProjectRead:
    try:
        project = await service.create_project(
            user_id=current_user.id,
            name=project_data.name,
            description=project_data.description,
            website_url=project_data.website_url,
            brand_name=project_data.brand_name,
            organization_id=project_data.organization_id,
        )
        return ProjectRead.model_validate(_project_to_dict(project))
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

@router.get("/", response_model=List[ProjectRead])
async def list_projects(
    service: ProjectService = Depends(get_project_service),
    current_user: UserTable = Depends(get_current_user),
) -> List[ProjectRead]:
    projects = await service.list_user_projects(user_id=current_user.id)
    return [ProjectRead.model_validate(_project_to_dict(project, prompt_count, model_count)) for project, prompt_count, model_count in projects]

@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int,
    service: ProjectService = Depends(get_project_service),
    current_user: UserTable = Depends(get_current_user),
) -> ProjectRead:
    try:
        project = await service.get_project(project_id=project_id, user_id=current_user.id)
        return ProjectRead.model_validate(_project_to_dict(project))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

@router.put("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
    current_user: UserTable = Depends(get_current_user),
) -> ProjectRead:
    try:
        if not await service.project_repo.can_manage_project(project_id, current_user.id): raise HTTPException(403, "Project manager role required")
        project = await service.get_project(project_id=project_id, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    try:
        updated_project = await service.update_project(
            project=project,
            name=project_data.name,
            description=project_data.description,
            website_url=project_data.website_url,
        )
        return ProjectRead.model_validate(_project_to_dict(updated_project))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    service: ProjectService = Depends(get_project_service),
    current_user: UserTable = Depends(get_current_user),
) -> None:
    try:
        if not await service.project_repo.can_manage_project(project_id, current_user.id): raise HTTPException(403, "Project manager role required")
        project = await service.get_project(project_id=project_id, user_id=current_user.id)
        await service.delete_project(project=project)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

@router.get("/{project_id}/brands", response_model=list[ProjectBrandRead])
async def list_project_brands(project_id: int, session: AsyncSession = Depends(get_session), current_user: UserTable = Depends(get_current_user)):
    if not await ProjectRepository(session).can_read(project_id, current_user.id): raise HTTPException(404, "Project not found")
    return (await session.execute(select(ProjectBrand).where(ProjectBrand.project_id == project_id).order_by(ProjectBrand.kind, ProjectBrand.name))).scalars().all()

@router.get("/{project_id}/observed-brands", response_model=list[ObservedBrandRead])
async def list_observed_brands(project_id: int, session: AsyncSession = Depends(get_session), current_user: UserTable = Depends(get_current_user)):
    if not await ProjectRepository(session).can_read(project_id, current_user.id): raise HTTPException(404, "Project not found")
    rows = await session.execute(
        select(Brand.id, Brand.name, Brand.domain)
        .join(RunBrand, RunBrand.brand_id == Brand.id)
        .join(AIRun, AIRun.id == RunBrand.ai_run_id)
        .join(Prompt, Prompt.id == AIRun.prompt_id)
        .where(Prompt.project_id == project_id)
        .distinct()
        .order_by(Brand.name)
    )
    return [ObservedBrandRead(brand_id=brand_id, name=name, domain=domain) for brand_id, name, domain in rows.all()]

@router.post("/{project_id}/brands", response_model=ProjectBrandRead, status_code=201)
async def add_project_brand(project_id: int, data: ProjectBrandCreate, session: AsyncSession = Depends(get_session), current_user: UserTable = Depends(get_current_user)):
    if not await ProjectRepository(session).can_write(project_id, current_user.id): raise HTTPException(403, "Write role required")
    if not await ProjectRepository(session).can_read(project_id, current_user.id): raise HTTPException(404, "Project not found")
    item = ProjectBrand(project_id=project_id, **data.model_dump()); session.add(item); await session.commit(); await session.refresh(item); return item

@router.delete("/{project_id}/brands/{brand_id}", status_code=204)
async def delete_project_brand(project_id: int, brand_id: int, session: AsyncSession = Depends(get_session), current_user: UserTable = Depends(get_current_user)):
    if not await ProjectRepository(session).can_write(project_id, current_user.id): raise HTTPException(403, "Write role required")
    if not await ProjectRepository(session).can_read(project_id, current_user.id): raise HTTPException(404, "Project not found")
    item = await session.scalar(select(ProjectBrand).where(ProjectBrand.id == brand_id, ProjectBrand.project_id == project_id))
    if not item: raise HTTPException(404, "Brand not found")
    await session.delete(item); await session.commit()

@router.get("/{project_id}/alerts")
async def list_alerts(project_id: int, session: AsyncSession = Depends(get_session), current_user: UserTable = Depends(get_current_user)):
    if not await ProjectRepository(session).can_read(project_id, current_user.id): raise HTTPException(404, "Project not found")
    return (await session.execute(select(Alert).where(Alert.project_id == project_id).order_by(Alert.created_at.desc()).limit(100))).scalars().all()

@router.post("/{project_id}/alert-rules")
async def add_alert_rule(project_id: int, kind: str, cooldown_hours: int = 24, session: AsyncSession = Depends(get_session), current_user: UserTable = Depends(get_current_user)):
    if not await ProjectRepository(session).can_write(project_id, current_user.id): raise HTTPException(403, "Write role required")
    if kind not in {"rank_drop", "disappearance", "new_competitor", "run_failure"}: raise HTTPException(422, "Invalid alert type")
    if not await ProjectRepository(session).can_read(project_id, current_user.id): raise HTTPException(404, "Project not found")
    rule = AlertRule(project_id=project_id, kind=kind, cooldown_hours=cooldown_hours); session.add(rule); await session.commit(); await session.refresh(rule); return rule

@router.post("/{project_id}/alerts/{alert_id}/read", status_code=204)
async def read_alert(project_id: int, alert_id: int, session: AsyncSession = Depends(get_session), current_user: UserTable = Depends(get_current_user)):
    if not await ProjectRepository(session).can_read(project_id, current_user.id): raise HTTPException(404, "Project not found")
    item = await session.scalar(select(Alert).where(Alert.id == alert_id, Alert.project_id == project_id))
    if not item: raise HTTPException(404, "Alert not found")
    item.read_at = datetime.now(timezone.utc); await session.commit()
