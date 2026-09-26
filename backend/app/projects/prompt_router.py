import asyncio
import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_session
from app.database.connection import async_session_maker
from app.database.models import AIModel, Prompt, UserTable
from app.repositories.prompt_repository import PromptRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.ai_run_repository import AIRunRepository
from app.services.prompt_service import PromptService
from app.services.ai_service import AIService
from app.services.ai_run_service import AIRunService
from app.services.brand_extraction_service import BrandExtractionService
from app.services.brand_persistence_service import BrandPersistenceService
from app.infrastructure.redis_client import get_redis
from app.infrastructure.run_queue import PromptRunQueue
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.projects.schema import PromptCreate, PromptRead
from app.projects.ai_models_schema import AIModelRead
from app.projects.ai_runs_schema import AIRunResult, PromptModelExecutionAvailability
from app.auth.fastapi_users import fastapi_users
from app.core.config import settings

logger = logging.getLogger(__name__)
_manual_run_lock = asyncio.Lock()
_manual_last_request_at = 0.0

router = APIRouter(prefix="/projects/{project_id}/prompts", tags=["prompts"])

def get_prompt_service(
    session: AsyncSession = Depends(get_session)
) -> PromptService:
    prompt_repo = PromptRepository(session)
    project_repo = ProjectRepository(session)
    return PromptService(prompt_repo, project_repo)


def get_ai_run_service(session: AsyncSession = Depends(get_session)) -> AIRunService:
    ai_service = AIService()
    return AIRunService(
        AIRunRepository(session),
        ai_service,
        BrandExtractionService(ai_service, session),
        BrandPersistenceService(session),
        PromptRunQueue(get_redis()),
        SystemSettingsRepository(session),
    )

async def require_project_writer(project_id: int, user_id: int, session: AsyncSession) -> None:
    if not await ProjectRepository(session).can_write(project_id, user_id):
        raise HTTPException(status_code=403, detail="Write role required")

async def get_current_user(
    user: UserTable = Depends(fastapi_users.current_user())
) -> UserTable:
    return user


async def prompt_read(prompt: Prompt, session: AsyncSession) -> PromptRead:
    active_rows = await session.execute(select(AIModel.model_key).where(AIModel.is_active.is_(True)))
    active_model_keys = {key.rsplit('/', 1)[-1] for (key,) in active_rows}
    models = []
    for link in prompt.models:
        model = AIModelRead.model_validate(link.model)
        model.is_active = model.model_key.rsplit('/', 1)[-1] in active_model_keys
        models.append(model)
    return PromptRead(
        id=prompt.id,
        project_id=prompt.project_id,
        text=prompt.text,
        is_active=prompt.is_active,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
        last_run_at=prompt.last_run_at,
        models=models,
    )

@router.post("", response_model=PromptRead, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    project_id: int,
    prompt_data: PromptCreate,
    service: PromptService = Depends(get_prompt_service),
    current_user: UserTable = Depends(get_current_user),
) -> PromptRead:
    try:
        await require_project_writer(project_id, current_user.id, service.prompt_repo.session)
                # Verify project ownership — get_by_id filters by user_id
        project_repo = ProjectRepository(service.prompt_repo.session)
        project = await project_repo.get_by_id(project_id, current_user.id)
        if not project:
            raise ValueError("پروژه یافت نشد یا دسترسی ندارید")

        prompt = await service.create_prompt(project_id, prompt_data.text, prompt_data.model_ids)
        return await prompt_read(prompt, service.prompt_repo.session)
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
        return [await prompt_read(p, service.prompt_repo.session) for p in prompts]
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

        return await prompt_read(prompt, service.prompt_repo.session)
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

@router.post("/{prompt_id}/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_prompt_model(
    project_id: int,
    prompt_id: int,
    model_id: int,
    service: PromptService = Depends(get_prompt_service),
    current_user: UserTable = Depends(get_current_user),
) -> None:
    try:
        await require_project_writer(project_id, current_user.id, service.prompt_repo.session)
        project_repo = ProjectRepository(service.prompt_repo.session)
        project = await project_repo.get_by_id(project_id, current_user.id)
        if not project:
            raise ValueError("پروژه یافت نشد یا دسترسی ندارید")

        prompt = await service.get_prompt(prompt_id)
        if prompt.project_id != project_id:
            raise ValueError("Prompt متعلق به این پروژه نیست")

        await service.add_prompt_model(prompt_id, model_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
        await require_project_writer(project_id, current_user.id, service.prompt_repo.session)
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

async def _execute_prompt_run(prompt_id: int, ai_model_id: int | None) -> None:
    try:
        async with async_session_maker() as session:
            ai_service = AIService()
            run_service = AIRunService(
                AIRunRepository(session),
                ai_service,
                BrandExtractionService(ai_service, session),
                BrandPersistenceService(session),
                PromptRunQueue(get_redis()),
                SystemSettingsRepository(session),
            )
            prompt = await PromptRepository(session).get_by_id(prompt_id)
            if prompt is None or not prompt.is_active:
                return
            if ai_model_id is not None:
                await run_service.run_prompt_model(prompt, ai_model_id, source="manual")
            else:
                global _manual_last_request_at
                for link in prompt.models:
                    async with _manual_run_lock:
                        wait = settings.WORKER_REQUEST_DELAY_SECONDS - (asyncio.get_running_loop().time() - _manual_last_request_at)
                        if wait > 0:
                            await asyncio.sleep(wait)
                        _manual_last_request_at = asyncio.get_running_loop().time()
                        try:
                            await run_service.run_prompt_model(prompt, link.model.id, source="manual")
                        except Exception:
                            logger.exception("prompt_manual_model_failed", extra={"event_data": {"prompt_id": prompt.id, "ai_model_id": link.model.id}})
    except Exception:
        logger.exception("prompt_run_background_failed", extra={"event_data": {"prompt_id": prompt_id, "ai_model_id": ai_model_id}})


def _queued_results(count: int) -> list[AIRunResult]:
    return [
        AIRunResult(
            ai_run_id=0,
            ai_run_status="queued",
            extraction_status="pending",
            brands_found=0,
            new_brands=0,
            existing_brands=0,
        )
        for _ in range(count)
    ]


@router.post("/{prompt_id}/run", response_model=List[AIRunResult])
async def run_prompt(
    project_id: int,
    prompt_id: int,
    background_tasks: BackgroundTasks,
    ai_model_id: int | None = Query(None, gt=0),
    prompt_service: PromptService = Depends(get_prompt_service),
    current_user: UserTable = Depends(get_current_user),
) -> list[AIRunResult]:
    try:
        await require_project_writer(project_id, current_user.id, prompt_service.prompt_repo.session)
        project_repo = ProjectRepository(prompt_service.prompt_repo.session)
        project = await project_repo.get_by_id(project_id, current_user.id)
        if not project:
            raise ValueError("پروژه یافت نشد یا دسترسی ندارید")

        prompt = await prompt_service.get_prompt(prompt_id)
        if prompt.project_id != project_id:
            raise ValueError("Prompt متعلق به این پروژه نیست")
        if not prompt.is_active:
            raise ValueError("Prompt آرشیو شده قابل اجرا نیست")
        if not prompt.models:
            raise ValueError("هیچ مدل AI برای این Prompt انتخاب نشده است")

        if ai_model_id is not None:
            background_tasks.add_task(_execute_prompt_run, prompt_id, ai_model_id)
            return _queued_results(1)
        background_tasks.add_task(_execute_prompt_run, prompt_id, None)
        return _queued_results(len(prompt.models))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{prompt_id}/execution-availability", response_model=List[PromptModelExecutionAvailability])
async def execution_availability(
    project_id: int,
    prompt_id: int,
    prompt_service: PromptService = Depends(get_prompt_service),
    run_service: AIRunService = Depends(get_ai_run_service),
    current_user: UserTable = Depends(get_current_user),
) -> list[dict]:
    project_repo = ProjectRepository(prompt_service.prompt_repo.session)
    project = await project_repo.get_by_id(project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    try:
        prompt = await prompt_service.get_prompt(prompt_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if prompt.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
    return await run_service.execution_availability(prompt)

@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_prompt(
    project_id: int,
    prompt_id: int,
    service: PromptService = Depends(get_prompt_service),
    current_user: UserTable = Depends(get_current_user),
) -> None:
    try:
        await require_project_writer(project_id, current_user.id, service.prompt_repo.session)
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

@router.post("/{prompt_id}/restore", response_model=PromptRead)
async def restore_prompt(
    project_id: int,
    prompt_id: int,
    service: PromptService = Depends(get_prompt_service),
    current_user: UserTable = Depends(get_current_user),
) -> PromptRead:
    try:
        await require_project_writer(project_id, current_user.id, service.prompt_repo.session)
        project_repo = ProjectRepository(service.prompt_repo.session)
        project = await project_repo.get_by_id(project_id, current_user.id)
        if not project:
            raise ValueError("پروژه یافت نشد یا دسترسی ندارید")

        prompt = await service.get_prompt(prompt_id)
        if prompt.project_id != project_id:
            raise ValueError("Prompt متعلق به این پروژه نیست")

        return await prompt_read(await service.restore_prompt(prompt_id), service.prompt_repo.session)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
