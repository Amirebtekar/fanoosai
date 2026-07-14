"""
Runnable self-check for AI Model Management (no frameworks).
Run: python backend/tests/test_ai_models.py
"""
import asyncio
import sys

sys.path.insert(0, "backend")

from app.core.config import settings
from app.database.models import AIModel, Prompt
from app.projects.ai_models_schema import AIModelRead
from app.repositories.ai_model_repository import AIModelRepository
from app.services.ai_model_service import AIModelService
from app.services.prompt_service import PromptService


class FakeRepo(AIModelRepository):
    def __init__(self):
        self._models = [
            AIModel(id=1, name="GPT-5", provider="OpenAI", model_key="openai/gpt-5", is_active=True),
            AIModel(id=2, name="Gemini", provider="Google", model_key="google/gemini-2.5-pro", is_active=True),
            AIModel(id=3, name="Old", provider="X", model_key="x/old", is_active=False),
        ]

    async def list_active(self):
        return [m for m in self._models if m.is_active]

    async def sync_from_gateway(self, rows):
        self._models = [AIModel(id=i + 1, is_active=True, **row) for i, row in enumerate(rows)]
        return self._models


async def test_list_active_only_returns_active():
    service = AIModelService(FakeRepo())
    models = await service.list_active_models()
    assert len(models) == 2, f"expected 2 active, got {len(models)}"
    keys = {m.model_key for m in models}
    assert keys == {"openai/gpt-5", "google/gemini-2.5-pro"}
    print("PASS: list_active_models returns active models only")


async def test_schema_serializes():
    m = AIModel(id=1, name="GPT-5", provider="OpenAI", model_key="openai/gpt-5", is_active=True)
    r = AIModelRead.model_validate(m)
    assert r.provider == "OpenAI"
    assert r.model_key == "openai/gpt-5"
    print("PASS: AIModelRead serializes from model")


async def test_gateway_base_url_configured():
    assert settings.AI_GATEWAY_BASE_URL.endswith("/api"), "AI Gateway base URL must point to gateway"
    print(f"PASS: AI_GATEWAY_BASE_URL = {settings.AI_GATEWAY_BASE_URL}")

async def test_openai_models_payload_normalizes():
    payload = {"data": [{"id": "openai/gpt-5", "owned_by": "OpenAI"}]}
    models = AIModelService._normalize_gateway_models(payload)
    assert models == [{"name": "openai/gpt-5", "provider": "OpenAI", "model_key": "openai/gpt-5"}]
    print("PASS: OpenAI-compatible /v1/models payload normalizes")

async def test_sync_gateway_models_saves_to_repo():
    service = AIModelService(FakeRepo())
    service.list_gateway_models = lambda: asyncio.sleep(0, [{"name": "GPT-5", "provider": "OpenAI", "model_key": "openai/gpt-5"}])
    models = await service.sync_gateway_models()
    assert models[0].model_key == "openai/gpt-5"
    print("PASS: sync_gateway_models saves gateway rows to repo")

class FakePromptRepo:
    async def get_by_id(self, prompt_id):
        return Prompt(id=prompt_id, project_id=1, text="x", is_active=True)

    async def remove_model(self, prompt_id, model_id):
        return prompt_id == 1 and model_id == 2

async def test_remove_prompt_model_requires_existing_link():
    service = PromptService(FakePromptRepo(), None)
    await service.remove_prompt_model(1, 2)
    try:
        await service.remove_prompt_model(1, 3)
    except ValueError as e:
        assert str(e) == "این مدل برای Prompt انتخاب نشده است"
    else:
        raise AssertionError("expected missing prompt model link to fail")
    print("PASS: prompt model can be removed and missing links fail")

if __name__ == "__main__":
    asyncio.run(test_list_active_only_returns_active())
    asyncio.run(test_schema_serializes())
    asyncio.run(test_gateway_base_url_configured())
    asyncio.run(test_openai_models_payload_normalizes())
    asyncio.run(test_sync_gateway_models_saves_to_repo())
    asyncio.run(test_remove_prompt_model_requires_existing_link())
    print("\nSelf-check complete.")
