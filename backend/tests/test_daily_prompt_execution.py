from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.ai_run_service import AIRunService


class FakeRunRepository:
    def __init__(self):
        self.claims = set()
        self.created = []

    async def claim_daily_run(self, prompt_id, ai_model_id, run_date):
        key = (prompt_id, ai_model_id, run_date)
        if key in self.claims:
            return False
        self.claims.add(key)
        return True

    async def create(self, **kwargs):
        run = SimpleNamespace(
            id=len(self.created) + 1,
            extraction_status="pending",
            status=kwargs["status"],
        )
        self.created.append(run)
        return run

    async def update_extraction(self, run, status, error=None):
        run.extraction_status = status


class FakeAIService:
    def __init__(self):
        self.calls = []

    async def run_prompt(self, model_key, request_text):
        self.calls.append((model_key, request_text))
        return "response"


class FakeExtractionService:
    async def extract(self, response):
        return SimpleNamespace(brands=[])


class FakePersistenceService:
    async def persist(self, run_id, extraction):
        return SimpleNamespace(new_brands=0, existing_brands=0)


@pytest.mark.asyncio
async def test_each_prompt_model_runs_once_per_day_and_again_the_next_day():
    repository = FakeRunRepository()
    ai_service = FakeAIService()
    service = AIRunService(
        repository,
        ai_service,
        FakeExtractionService(),
        FakePersistenceService(),
    )
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[
            SimpleNamespace(model=SimpleNamespace(id=1, model_key="model-a")),
            SimpleNamespace(model=SimpleNamespace(id=2, model_key="model-b")),
        ],
    )

    first_day = datetime(2026, 7, 17)
    assert len(await service.run_prompt_models(prompt, now=first_day)) == 2
    assert len(await service.run_prompt_models(prompt, now=first_day)) == 0
    assert len(await service.run_prompt_models(prompt, now=datetime(2026, 7, 18))) == 2
    assert len(ai_service.calls) == 4
