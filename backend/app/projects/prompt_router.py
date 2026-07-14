from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.dependencies import get_session
from app.database.models import Prompt, UserTable
from app.repositories.prompt_repository import PromptRepository
from app.repositories.project_repository import ProjectRepository
from app.services.prompt_service import PromptService
from app.projects.schema import PromptCreate, PromptRead
from app.projects.ai_models_schema import AIModelRead
from app.auth.fastapi_users import fastapi_users

router = APIRouter(prefix="/projects/{project_id}/prompts", tags=["prompts"])

def get_prompt_service(
    session: AsyncSession = Depends(get_session)
) -> PromptService:
    prompt_repo = PromptRepository(session)
    project_repo = ProjectRepository(session)
    return PromptService(prompt_repo, project_repo)

async def get_current_user(
    user: UserTable = Depends(fastapi_users.current_user())
) -> UserTable:
    return user


def prompt_read(prompt: Prompt) -> PromptRead:
    return PromptRead(
        id=prompt.id,
        project_id=prompt.project_id,
        text=prompt.text,
        is_active=prompt.is_active,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        models=[AIModelRead.model_validate(link.model) for link in prompt.models],
    )

@router.post("", response_model=PromptRead, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    project_id: int,
    prompt_data: PromptCreate,
    service: PromptService = Depends(get_prompt_service),
    current_user: UserTable = Depends(get_current_user),
) -> PromptRead:
    try:
                # Verify project ownership — get_by_id filters by user_id
        project_repo = ProjectRepository(service.prompt_repo.session)
        project = await project_repo.get_by_id(project_id, current_user.id)
        if not project:
            raise ValueError("پروژه یافت نشد یا دسترسی ندارید")

        prompt = await service.create_prompt(project_id, prompt_data.text, prompt_data.model_ids)
        return prompt_read(prompt)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

@router.get("", response_model=List[PromptRead])
async def list_prompts(
    project_id: int,
    include_archived: bool = Query(False, description="شامل Prompt های آرشیو شده"),
    service: PromptService = Depends(get_prompt_service),
    current_user: UserTable = Depends(get_current_user),
) -> List[PromptRead]:
    try:
        # Verify project ownership
        project_repo = ProjectRepository(service.prompt_repo.session)
        project = await project_repo.get_by_id(project_id, current_user.id)
        if not project:
            raise ValueError("پروژه یافت نشد یا دسترسی ندارید")

        prompts = await service.list_project_prompts(project_id, include_archived)
        return [prompt_read(p) for p in prompts]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

@router.get("/{prompt_id}", response_model=PromptRead)
async def get_prompt(
    project_id: int,
    prompt_id: int,
    service: PromptService = Depends(get_prompt_service),
    current_user: UserTable = Depends(get_current_user),
) -> PromptRead:
    try:
        # Verify project ownership
        project_repo = ProjectRepository(service.prompt_repo.session)
        project = await project_repo.get_by_id(project_id, current_user.id)
        if not project:
            raise ValueError("پروژه یافت نشد یا دسترسی ندارید")

        prompt = await service.get_prompt(prompt_id)
        if prompt.project_id != project_id:
            raise ValueError("Prompt متعلق به این پروژه نیست")

        return prompt_read(prompt)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

@router.get("/{prompt_id}/models", response_model=List[AIModelRead])
async def list_prompt_models(
    project_id: int,
    prompt_id: int,
    service: PromptService = Depends(get_prompt_service),
    current_user: UserTable = Depends(get_current_user),
) -> List[AIModelRead]:
    try:
        project_repo = ProjectRepository(service.prompt_repo.session)
        project = await project_repo.get_by_id(project_id, current_user.id)
        if not project:
            raise ValueError("پروژه یافت نشد یا دسترسی ندارید")

        prompt = await service.get_prompt(prompt_id)
        if prompt.project_id != project_id:
            raise ValueError("Prompt متعلق به این پروژه نیست")

        return [AIModelRead.model_validate(link.model) for link in prompt.models]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

@router.delete("/{prompt_id}/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_prompt_model(
    project_id: int,
    prompt_id: int,
    model_id: int,
    service: PromptService = Depends(get_prompt_service),
    current_user: UserTable = Depends(get_current_user),
) -> None:
    try:
        project_repo = ProjectRepository(service.prompt_repo.session)
        project = await project_repo.get_by_id(project_id, current_user.id)
        if not project:
            raise ValueError("پروژه یافت نشد یا دسترسی ندارید")

        prompt = await service.get_prompt(prompt_id)
        if prompt.project_id != project_id:
            raise ValueError("Prompt متعلق به این پروژه نیست")

        await service.remove_prompt_model(prompt_id, model_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_prompt(
    project_id: int,
    prompt_id: int,
    service: PromptService = Depends(get_prompt_service),
    current_user: UserTable = Depends(get_current_user),
) -> None:
    try:
        # Verify project ownership
        project_repo = ProjectRepository(service.prompt_repo.session)
        project = await project_repo.get_by_id(project_id, current_user.id)
        if not project:
            raise ValueError("پروژه یافت نشد یا دسترسی ندارید")

        prompt = await service.get_prompt(prompt_id)
        if prompt.project_id != project_id:
            raise ValueError("Prompt متعلق به این پروژه نیست")

        await service.archive_prompt(prompt_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )