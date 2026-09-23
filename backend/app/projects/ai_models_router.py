from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.dependencies import get_session
from app.repositories.ai_model_repository import AIModelRepository
from app.services.ai_model_service import AIModelService
from app.projects.ai_models_schema import AIModelRead
from app.auth.fastapi_users import fastapi_users
from app.database.models import UserTable
from app.database.models import AIModel, AIRun
from sqlalchemy import select, func

router = APIRouter(prefix="/ai-models", tags=["ai-models"])

def get_ai_model_service(session: AsyncSession = Depends(get_session)) -> AIModelService:
    return AIModelService(AIModelRepository(session))

@router.get("", response_model=List[AIModelRead])
async def list_active_models(
    service: AIModelService = Depends(get_ai_model_service),
    _: UserTable = Depends(fastapi_users.current_user(active=True)),
) -> List[AIModelRead]:
    models = await service.list_active_models()
    return [AIModelRead.model_validate(m) for m in models]

@router.get("/admin", response_model=List[AIModelRead])
async def list_all_models(session: AsyncSession = Depends(get_session), _: UserTable = Depends(fastapi_users.current_user(active=True, superuser=True))):
    return (await session.execute(select(AIModel).order_by(AIModel.name))).scalars().all()


@router.post("/sync", response_model=List[AIModelRead])
async def sync_gateway_models(
    service: AIModelService = Depends(get_ai_model_service),
    _: UserTable = Depends(fastapi_users.current_user(active=True, superuser=True)),
) -> List[AIModelRead]:
    try:
        await service.sync_gateway_models()
        models = (await service.repo.session.execute(select(AIModel).order_by(AIModel.name))).scalars().all()
        return [AIModelRead.model_validate(m) for m in models]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/gateway")
async def list_gateway_models(
    service: AIModelService = Depends(get_ai_model_service),
    _: UserTable = Depends(fastapi_users.current_user(active=True, superuser=True)),
) -> list[dict]:
    try:
        return await service.list_gateway_models()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))

@router.patch("/{model_id}", response_model=AIModelRead)
async def set_model_active(model_id: int, is_active: bool, session: AsyncSession = Depends(get_session), _: UserTable = Depends(fastapi_users.current_user(active=True, superuser=True))):
    model = await session.get(AIModel, model_id)
    if not model: raise HTTPException(404, "Model not found")
    model.is_active = is_active; await session.commit(); await session.refresh(model); return model

@router.get("/{model_id}/health")
async def model_health(model_id: int, session: AsyncSession = Depends(get_session), _: UserTable = Depends(fastapi_users.current_user(active=True, superuser=True))):
    if not await session.get(AIModel, model_id): raise HTTPException(404, "Model not found")
    total, failed, latest = (await session.execute(select(func.count(AIRun.id), func.count(AIRun.id).filter(AIRun.status != "success"), func.max(AIRun.created_at)).where(AIRun.ai_model_id == model_id))).one()
    return {"total_runs": total, "failed_runs": failed, "last_run": latest}
