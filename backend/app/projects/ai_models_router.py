from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.dependencies import get_session
from app.repositories.ai_model_repository import AIModelRepository
from app.services.ai_model_service import AIModelService
from app.projects.ai_models_schema import AIModelRead
from app.auth.fastapi_users import fastapi_users
from app.database.models import UserTable

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


@router.post("/sync", response_model=List[AIModelRead])
async def sync_gateway_models(
    service: AIModelService = Depends(get_ai_model_service),
    _: UserTable = Depends(fastapi_users.current_user(active=True, superuser=True)),
) -> List[AIModelRead]:
    try:
        models = await service.sync_gateway_models()
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
