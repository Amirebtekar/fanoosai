import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services.ai_run_service import AIRunService


class FakeRunRepository:
    def __init__(self):
        self.claims = set()
        self.created = []
        self.claim_sources = {}

    async def claim_daily_run(self, prompt_id, ai_model_id, run_date, source):
        key = (prompt_id, ai_model_id, run_date)
        if key in self.claims:
            return False
        self.claims.add(key)
        self.claim_sources[key] = source
        return True

    async def get_daily_claim_sources(self, prompt_id, ai_model_ids, run_date):
        return {
            model_id: self.claim_sources[(claimed_prompt_id, model_id, claimed_date)]
            for claimed_prompt_id, model_id, claimed_date in self.claims
            if claimed_prompt_id == prompt_id and model_id in ai_model_ids and claimed_date == run_date
        }

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


@pytest.mark.asyncio
async def test_manual_and_scheduled_runs_share_the_daily_quota_and_record_the_source():
    repository = FakeRunRepository()
    service = AIRunService(
        repository,
        FakeAIService(),
        FakeExtractionService(),
        FakePersistenceService(),
    )
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[SimpleNamespace(model=SimpleNamespace(id=1, model_key="model-a"))],
    )

    today = datetime(2026, 7, 17)
    assert len(await service.run_prompt_models(prompt, now=today, source="manual")) == 1
    assert await service.run_prompt_models(prompt, now=today, source="scheduled") == []
    assert set(repository.claim_sources.values()) == {"manual"}


@pytest.mark.asyncio
async def test_scheduler_first_blocks_manual_and_concurrent_requests_claim_once():
    repository = FakeRunRepository()
    ai_service = FakeAIService()
    service = AIRunService(repository, ai_service, FakeExtractionService(), FakePersistenceService())
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[SimpleNamespace(model=SimpleNamespace(id=1, model_key="model-a"))],
    )
    today = datetime(2026, 7, 17)

    assert len(await service.run_prompt_models(prompt, now=today, source="scheduled")) == 1
    assert await service.run_prompt_models(prompt, now=today, source="manual") == []

    tomorrow = datetime(2026, 7, 18)
    results = await asyncio.gather(
        service.run_prompt_models(prompt, now=tomorrow),
        service.run_prompt_models(prompt, now=tomorrow),
    )
    assert sum(len(result) for result in results) == 1
    assert len(ai_service.calls) == 2


@pytest.mark.asyncio
async def test_daily_claim_uses_tehran_date_at_a_utc_midnight_boundary():
    repository = FakeRunRepository()
    service = AIRunService(repository, FakeAIService(), FakeExtractionService(), FakePersistenceService())
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[SimpleNamespace(model=SimpleNamespace(id=1, model_key="model-a"))],
    )

    assert len(await service.run_prompt_models(prompt, now=datetime(2026, 7, 17, 20, 29, tzinfo=timezone.utc))) == 1
    assert len(await service.run_prompt_models(prompt, now=datetime(2026, 7, 17, 20, 31, tzinfo=timezone.utc))) == 1


@pytest.mark.asyncio
async def test_execution_availability_reports_today_claim_source_per_model():
    repository = FakeRunRepository()
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[
            SimpleNamespace(model=SimpleNamespace(id=1, name="model-a", model_key="model-a")),
            SimpleNamespace(model=SimpleNamespace(id=2, name="model-b", model_key="model-b")),
        ],
    )
    service = AIRunService(repository, FakeAIService(), FakeExtractionService(), FakePersistenceService())
    today = datetime(2026, 7, 17)
    await service.run_prompt_models(prompt, now=today, source="scheduled")

    assert await service.execution_availability(prompt, now=today) == [
        {"model_id": 1, "model_name": "model-a", "can_run": False, "claim_source": "scheduled"},
        {"model_id": 2, "model_name": "model-b", "can_run": False, "claim_source": "scheduled"},
    ]
