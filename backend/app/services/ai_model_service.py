import aiohttp

from app.core.config import settings
from app.database.models import AIModel
from app.repositories.ai_model_repository import AIModelRepository


class AIModelService:
    def __init__(self, repo: AIModelRepository):
        self.repo = repo

    async def list_active_models(self) -> list[AIModel]:
        return await self.repo.list_active()

    async def sync_gateway_models(self) -> list[AIModel]:
        rows = await self.list_gateway_models()
        return await self.repo.sync_from_gateway(rows)

    async def list_gateway_models(self) -> list[dict]:
        headers = {"Accept": "application/json"}
        if settings.AI_GATEWAY_API_KEY:
            headers["Authorization"] = f"Bearer {settings.AI_GATEWAY_API_KEY}"

        url = f"{settings.AI_GATEWAY_BASE_URL.rstrip('/')}/v1/models"
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=20) as response:
                if response.status >= 400:
                    raise ValueError("AI Gateway model listing failed")
                payload = await response.json()

        return self._normalize_gateway_models(payload)

    @staticmethod
    def _normalize_gateway_models(payload: dict) -> list[dict]:
        rows = payload.get("data", payload if isinstance(payload, list) else [])
        return [
            {
                "name": item.get("name") or item.get("id"),
                "provider": item.get("owned_by") or item.get("provider") or "Gateway",
                "model_key": item.get("id"),
            }
            for item in rows
            if item.get("id")
        ]
