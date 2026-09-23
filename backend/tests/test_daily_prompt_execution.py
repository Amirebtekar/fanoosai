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
        self.completed_claims = []
        self.released_claims = []

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

    async def complete_daily_run(self, prompt_id, ai_model_id, run_date):
        self.completed_claims.append((prompt_id, ai_model_id, run_date))

    async def release_daily_run(self, prompt_id, ai_model_id, run_date):
        key = (prompt_id, ai_model_id, run_date)
        self.released_claims.append(key)
        self.claims.discard(key)
        self.claim_sources.pop(key, None)

    async def create(self, **kwargs):
        run = SimpleNamespace(
            id=len(self.created) + 1,
            extraction_status="pending",
            **kwargs,
        )
        self.created.append(run)
        return run

    async def update_extraction(self, run, status, error=None):
        run.extraction_status = status
        run.error_message = error

    async def alert_run_failure(self, prompt_id, message):
        return None


class FakeAIService:
    def __init__(self):
        self.calls = []

    async def run_prompt(self, model_key, request_text):
        self.calls.append((model_key, request_text))
        return "response"

    async def run_prompt_with_provider(self, model_key, request_text):
        return await self.run_prompt(model_key, request_text), "primary"


class FailingAIService:
    async def run_prompt(self, model_key, request_text):
        raise ValueError("provider unavailable")

    async def run_prompt_with_provider(self, model_key, request_text):
        return await self.run_prompt(model_key, request_text), "primary"


class FakeRetryQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue_retry_in_one_hour(self, job):
        self.jobs.append(job)

    async def enqueue_extraction_retry_in_five_minutes(self, job):
        self.jobs.append(job)


class FakeExtractionService:
    async def extract(self, response):
        return SimpleNamespace(brands=[])


class FailingExtractionService:
    async def extract(self, response):
        raise ValueError("extractor unavailable")


class FakePersistenceService:
    async def persist(self, run_id, extraction):
        return SimpleNamespace(new_brands=0, existing_brands=0)


@pytest.mark.asyncio
async def test_run_appends_domain_formatting_instruction_to_the_user_prompt():
    repository = FakeRunRepository()
    ai_service = FakeAIService()
    service = AIRunService(repository, ai_service, FakeExtractionService(), FakePersistenceService())
    prompt = SimpleNamespace(
        id=7,
        text="معتبرترین ارائه‌دهنده خدمات ابری در ایران کیست؟",
        models=[SimpleNamespace(model=SimpleNamespace(id=1, model_key="model-a"))],
    )

    await service.run_prompt_models(prompt, now=datetime(2026, 7, 17))

    assert ai_service.calls == [(
        "model-a",
        "معتبرترین ارائه‌دهنده خدمات ابری در ایران کیست؟\n\n"
        "اگر نام برندی می‌آوری، دامنه رسمی آن را کنار نام به شکل «برند (example.com)» بنویس. "
        "دامنه را حدس نزن؛ اگر مطمئن نیستی، آن را نیاور. به این دستور در پاسخ اشاره نکن.",
    )]


@pytest.mark.asyncio
async def test_successful_run_records_the_provider_that_answered():
    class AvalAIFallback(FakeAIService):
        async def run_prompt_with_provider(self, model_key, request_text):
            self.calls.append((model_key, request_text))
            return "response", "avalai"

    repository = FakeRunRepository()
    service = AIRunService(
        repository,
        AvalAIFallback(),
        FakeExtractionService(),
        FakePersistenceService(),
    )
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[SimpleNamespace(model=SimpleNamespace(id=1, model_key="model-a"))],
    )

    await service.run_prompt_models(prompt, now=datetime(2026, 7, 17))

    assert repository.created[0].provider_used == "avalai"
    assert repository.completed_claims


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
        {"model_id": 1, "model_name": "model-a", "model_is_active": True, "can_run": False, "claim_source": "scheduled"},
        {"model_id": 2, "model_name": "model-b", "model_is_active": True, "can_run": False, "claim_source": "scheduled"},
    ]


@pytest.mark.asyncio
async def test_execution_availability_marks_inactive_models_unrunnable():
    repository = FakeRunRepository()
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[
            SimpleNamespace(model=SimpleNamespace(id=1, name="model-a", model_key="model-a", is_active=True)),
            SimpleNamespace(model=SimpleNamespace(id=2, name="gpt-chat", model_key="openai/gpt-5-chat", is_active=False)),
        ],
    )
    service = AIRunService(repository, FakeAIService(), FakeExtractionService(), FakePersistenceService())

    availability = await service.execution_availability(prompt, now=datetime(2026, 7, 17))

    assert availability == [
        {"model_id": 1, "model_name": "model-a", "model_is_active": True, "can_run": True, "claim_source": None},
        {"model_id": 2, "model_name": "gpt-chat", "model_is_active": False, "can_run": False, "claim_source": None},
    ]


@pytest.mark.asyncio
async def test_run_prompt_model_skips_inactive_model():
    repository = FakeRunRepository()
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[SimpleNamespace(model=SimpleNamespace(id=2, name="gpt-chat", model_key="openai/gpt-5-chat", is_active=False))],
    )
    service = AIRunService(repository, FakeAIService(), FakeExtractionService(), FakePersistenceService())

    results = await service.run_prompt_model(prompt, 2, now=datetime(2026, 7, 17))

    assert results == []
    assert repository.created == []


@pytest.mark.asyncio
async def test_failed_runs_retry_after_one_hour_up_to_three_total_attempts():
    queue = FakeRetryQueue()
    service = AIRunService(
        FakeRunRepository(), FailingAIService(), FakeExtractionService(), FakePersistenceService(), queue,
    )
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[SimpleNamespace(model=SimpleNamespace(id=1, name="model-a", model_key="model-a"))],
    )

    await service.run_prompt_models(prompt, now=datetime(2026, 7, 17), source="manual")
    first_retry = queue.jobs.pop()
    assert (first_retry.source, first_retry.run_attempt) == ("retry", 2)

    await service.run_prompt_model(prompt, 1, now=datetime(2026, 7, 17), source="retry", run_attempt=2)
    second_retry = queue.jobs.pop()
    assert (second_retry.source, second_retry.run_attempt) == ("retry", 3)

    await service.run_prompt_model(prompt, 1, now=datetime(2026, 7, 17), source="retry", run_attempt=3)
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_failed_manual_run_releases_claim_so_user_can_retry_same_day():
    repository = FakeRunRepository()
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[SimpleNamespace(model=SimpleNamespace(id=1, name="model-a", model_key="model-a"))],
    )
    service = AIRunService(
        repository, FailingAIService(), FakeExtractionService(), FakePersistenceService(),
    )
    today = datetime(2026, 7, 17)

    first = await service.run_prompt_model(prompt, 1, now=today, source="manual")
    assert first[0]["ai_run_status"] == "failed"
    assert repository.released_claims == [(7, 1, today.date())]
    assert repository.completed_claims == []

    availability = await service.execution_availability(prompt, now=today)
    assert availability[0]["can_run"] is True

    second = await service.run_prompt_model(prompt, 1, now=today, source="manual")
    assert len(second) == 1
    assert len(repository.created) == 2


@pytest.mark.asyncio
async def test_failed_brand_extraction_retries_in_five_minutes_without_rerunning_the_model():
    queue = FakeRetryQueue()
    service = AIRunService(
        FakeRunRepository(), FakeAIService(), FailingExtractionService(), FakePersistenceService(), queue,
    )
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[SimpleNamespace(model=SimpleNamespace(id=1, name="model-a", model_key="model-a"))],
    )

    result = await service.run_prompt_models(prompt, now=datetime(2026, 7, 17))

    assert result[0]["ai_run_status"] == "success"
    assert result[0]["extraction_status"] == "failed"
    assert (queue.jobs[0].source, queue.jobs[0].ai_run_id) == ("extraction_retry", 1)


@pytest.mark.asyncio
async def test_extraction_retry_stops_after_the_configured_attempt_limit(monkeypatch):
    run = SimpleNamespace(
        id=4,
        prompt_id=7,
        ai_model_id=1,
        status="success",
        extraction_status="failed",
        response_text="bad response",
    )

    class Repository(FakeRunRepository):
        async def get(self, run_id):
            return run

    queue = FakeRetryQueue()
    service = AIRunService(
        Repository(), FakeAIService(), FailingExtractionService(), FakePersistenceService(), queue,
    )

    await service.retry_extraction(4, run_attempt=3)

    assert run.extraction_status == "exhausted"
    assert queue.jobs == []


@pytest.mark.asyncio
async def test_unavailable_retry_queue_does_not_block_later_models():
    class FirstProviderFails(FakeAIService):
        async def run_prompt(self, model_key, request_text):
            self.calls.append((model_key, request_text))
            if model_key == "model-a":
                raise ValueError("provider unavailable")
            return "response"

    class UnavailableRetryQueue(FakeRetryQueue):
        async def enqueue_retry_in_one_hour(self, job):
            raise TimeoutError("redis unavailable")

    ai_service = FirstProviderFails()
    service = AIRunService(
        FakeRunRepository(), ai_service, FakeExtractionService(), FakePersistenceService(), UnavailableRetryQueue(),
    )
    prompt = SimpleNamespace(
        id=7,
        text="test prompt",
        models=[
            SimpleNamespace(model=SimpleNamespace(id=1, name="model-a", model_key="model-a")),
            SimpleNamespace(model=SimpleNamespace(id=2, name="model-b", model_key="model-b")),
        ],
    )

    results = await service.run_prompt_models(prompt, now=datetime(2026, 7, 17))

    assert [model for model, _ in ai_service.calls] == ["model-a", "model-b"]
    assert [result["ai_run_status"] for result in results] == ["failed", "success"]
