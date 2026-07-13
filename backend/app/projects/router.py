from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.dependencies import get_session
from app.database.models import UserTable, Project
from app.repositories.project_repository import ProjectRepository
from app.repositories.user_repository import UserRepository
from app.services.project_service import ProjectService
from app.projects.schema import ProjectCreate, ProjectUpdate, ProjectRead
from app.auth.fastapi_users import fastapi_users

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_to_dict(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "website_url": project.website_url,
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
        )
        return ProjectRead.model_validate(_project_to_dict(project))
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
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
    return [ProjectRead.model_validate(_project_to_dict(p)) for p in projects]

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
        project = await service.get_project(project_id=project_id, user_id=current_user.id)
        updated_project = await service.update_project(
            project=project,
            name=project_data.name,
            description=project_data.description,
            website_url=project_data.website_url,
        )
        return ProjectRead.model_validate(_project_to_dict(updated_project))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    service: ProjectService = Depends(get_project_service),
    current_user: UserTable = Depends(get_current_user),
) -> None:
    try:
        project = await service.get_project(project_id=project_id, user_id=current_user.id)
        await service.delete_project(project=project)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )