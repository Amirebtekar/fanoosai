import aiohttp

from app.core.config import settings
from app.database.models import AIModel
from app.repositories.ai_model_repository import AIModelRepository
from app.services.ai_service import avalai_model_key


class AIModelService:
    def __init__(self, repo: AIModelRepository):
        self.repo = repo

    async def list_active_models(self) -> list[AIModel]:
        return await self.repo.list_active()

    async def sync_gateway_models(self) -> list[AIModel]:
        rows = await self.list_gateway_models()
        return await self.repo.sync_from_gateway(rows)

    async def list_gateway_models(self) -> list[dict]:
        async with aiohttp.ClientSession() as session:
            avalai = await self._fetch_models(
                session,
                f"{settings.AVALAI_BASE_URL.rstrip('/')}/models",
                settings.AVALAI_API_KEY,
                "AvalAI",
            )
            if not settings.AI_GATEWAY_ENABLED:
                return self._normalize_gateway_models(avalai)
            parspack = await self._fetch_models(
                session,
                f"{settings.AI_GATEWAY_BASE_URL.rstrip('/')}/v1/models",
                settings.AI_GATEWAY_API_KEY,
                "AI Gateway",
            )
        return self._normalize_gateway_models(avalai)

    @staticmethod
    async def _fetch_models(
        session: aiohttp.ClientSession,
        url: str,
        api_key: str,
        provider: str,
    ) -> dict:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        async with session.get(url, headers=headers, timeout=20) as response:
            if response.status >= 400:
                raise ValueError(f"{provider} model listing failed")
            return await response.json()

    @classmethod
    def _common_gateway_models(cls, parspack: dict, avalai: dict) -> list[dict]:
        parspack_rows = cls._normalize_gateway_models(parspack)
        avalai_keys = {
            row["model_key"]
            for row in cls._normalize_gateway_models(avalai)
        }
        return [
            row
            for row in parspack_rows
            if row["model_key"] in avalai_keys
            or avalai_model_key(row["model_key"]) in avalai_keys
        ]

    @staticmethod
    def _normalize_gateway_models(payload: dict) -> list[dict]:
        rows = payload.get("data", payload if isinstance(payload, list) else [])
        return [
            {
                "name": item.get("id"),
                "provider": item.get("owned_by") or item.get("provider") or "Gateway",
                "model_key": item.get("id"),
            }
            for item in rows
            if item.get("id")
        ]
