"""Regression tests for brand extraction in the daily worker and the bounded retry.

Background: extraction failures in the daily worker were never marked as completed,
a rollback inside persistence expired ORM objects so the real error was overwritten
by MissingGreenlet, and the scheduler retried every failed run every minute.
"""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.ai_run_service import AIRunService
from app.services.daily_model_run_service import DailyModelRunService


class ExpiringPrompt:
    """Prompt whose attributes become unreadable once ``expired`` is set (like after a rollback)."""

    def __init__(self, prompt_id, text, models):
        self._id, self._text, self._models = prompt_id, text, models
        self.expired = False

    def _guard(self, value):
        if self.expired:
            raise RuntimeError("greenlet_spawn has not been called")
        return value

    @property
    def id(self):
        return self._guard(self._id)

    @property
    def text(self):
        return self._guard(self._text)

    @property
    def models(self):
        return self._guard(self._models)


class FakeDMRRepo:
    def __init__(self, models):
        self.rows = [SimpleNamespace(model=model, attempts=0) for model in models]
        self.success = []
        self.failures = []
        self.released = []

    async def ensure_rows(self, prompt_id, model_keys, run_date):
        return self.rows

    async def get_runnable(self, prompt_id, run_date, now=None):
        return list(self.rows)

    async def acquire_lock(self, prompt_id, model, run_date):
        return True

    async def release_lock(self, prompt_id, model, run_date):
        self.released.append(model)

    async def mark_success(self, prompt_id, model, run_date, run_id):
        self.success.append((model, run_id))

    async def mark_failure(self, prompt_id, model, run_date, **kwargs):
        self.failures.append(model)
        return "retrying"


class FakeRunRepo:
    def __init__(self):
        self.runs = []
        self.extraction_updates = []
        self.alerts = []
        self.session = SimpleNamespace(rollback=self._rollback)
        self.rollbacks = 0

    async def _rollback(self):
        self.rollbacks += 1

    async def create(self, **kwargs):
        run = SimpleNamespace(id=100 + len(self.runs), extraction_status="pending", **kwargs)
        self.runs.append(run)
        return run

    async def update_extraction(self, run, status, error=None):
        self.extraction_updates.append((run.id, status, error))
        run.extraction_status = status

    async def alert_new_competitor(self, prompt_id, names):
        self.alerts.append(("competitor", prompt_id))

    async def alert_rank_changes(self, run_id):
        self.alerts.append(("rank", run_id))

    async def alert_run_failure(self, prompt_id, message):
        return None


class FakeAI:
    last_usage = {}

    async def run_prompt_with_provider(self, model_key, text):
        return f"answer from {model_key}", "primary"


class Extraction:
    def __init__(self, fail_for=()):
        self.fail_for = set(fail_for)
        self.calls = []

    async def extract(self, text):
        self.calls.append(text)
        if any(model in text for model in self.fail_for):
            raise ValueError("Brand name and domain resolve to different identities; admin review is required")
        return SimpleNamespace(brands=[SimpleNamespace(name="ArvanCloud")])


class Persistence:
    def __init__(self, prompt=None):
        self.prompt = prompt
        self.persisted = []

    async def persist(self, run_id, extraction):
        self.persisted.append(run_id)
        return SimpleNamespace(new_brands=0, existing_brands=1, run_brands=1, skipped_brands=0)


def make_prompt(models):
    links = [SimpleNamespace(model=SimpleNamespace(id=index + 1, name=key, model_key=key, is_active=True)) for index, key in enumerate(models)]
    return ExpiringPrompt(29, "CDN?", links)


@pytest.mark.asyncio
async def test_daily_worker_marks_successful_extraction_completed():
    prompt = make_prompt(["gpt-6-luna"])
    run_repo = FakeRunRepo()
    service = DailyModelRunService(FakeDMRRepo(["gpt-6-luna"]), run_repo, FakeAI(), Extraction(), Persistence())

    results = await service.run_daily(prompt, run_date=date(2026, 10, 29))

    assert results[0]["status"] == "success"
    assert run_repo.extraction_updates == [(100, "completed", None)]
    assert ("rank", 100) in run_repo.alerts


@pytest.mark.asyncio
async def test_daily_worker_records_real_extraction_error_and_keeps_going_after_expiry():
    """The failure of one model must not hide its error or stop the next models."""
    prompt = make_prompt(["claude-opus-5-5", "grok-4.7"])
    run_repo = FakeRunRepo()

    class ExpireOnFailure(Extraction):
        async def extract(self, text):
            try:
                return await super().extract(text)
            except ValueError:
                prompt.expired = True  # what a session rollback does to loaded ORM objects
                raise

    dmr = FakeDMRRepo(["claude-opus-5-5", "grok-4.7"])
    service = DailyModelRunService(dmr, run_repo, FakeAI(), ExpireOnFailure(fail_for={"claude"}), Persistence())

    results = await service.run_daily(prompt, run_date=date(2026, 10, 29))

    assert [r["status"] for r in results] == ["success", "success"]
    assert run_repo.extraction_updates[0][1] == "failed"
    assert "different identities" in run_repo.extraction_updates[0][2]
    assert "greenlet" not in run_repo.extraction_updates[0][2]
    assert run_repo.extraction_updates[1] == (101, "completed", None)
    assert dmr.released == ["claude-opus-5-5", "grok-4.7"]
    assert [m for m, _ in dmr.success] == ["claude-opus-5-5", "grok-4.7"]


@pytest.mark.asyncio
async def test_daily_worker_survives_a_failing_status_update():
    prompt = make_prompt(["claude-opus-5-5"])
    run_repo = FakeRunRepo()

    async def broken_update(run, status, error=None):
        raise RuntimeError("db down")

    run_repo.update_extraction = broken_update
    service = DailyModelRunService(FakeDMRRepo(["claude-opus-5-5"]), run_repo, FakeAI(), Extraction(fail_for={"claude"}), Persistence())

    results = await service.run_daily(prompt, run_date=date(2026, 10, 29))

    assert results[0]["status"] == "success"
    assert run_repo.rollbacks == 1


class RetryRepo(FakeRunRepo):
    def __init__(self, candidates):
        super().__init__()
        self.candidates = candidates
        self.query = None

    async def get_failed_extractions(self, cutoff, **kwargs):
        self.query = {"cutoff": cutoff, **kwargs}
        rows = [c for c in self.candidates if kwargs.get("prompt_id") in (None, c[1])]
        limit = kwargs.get("limit")
        return rows[:limit] if limit else rows


@pytest.mark.asyncio
async def test_retry_is_bounded_by_batch_attempts_and_backoff(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "EXTRACTION_RETRY_BATCH_SIZE", 2)
    monkeypatch.setattr(settings, "EXTRACTION_MAX_ATTEMPTS", 4)
    monkeypatch.setattr(settings, "EXTRACTION_RETRY_BACKOFF_MINUTES", 30)
    repo = RetryRepo([(1, 29, "a"), (2, 29, "b"), (3, 29, "c")])
    service = AIRunService(repo, FakeAI(), Extraction(), Persistence())

    results = await service.retry_failed_extractions(older_than_hours=1)

    assert [r["run_id"] for r in results] == [1, 2]
    assert repo.query["limit"] == 2
    assert repo.query["max_attempts"] == 4
    now = datetime.now(timezone.utc)
    assert now - timedelta(minutes=31) < repo.query["retry_before"] < now - timedelta(minutes=29)
    assert now - timedelta(hours=1, minutes=1) < repo.query["cutoff"] < now - timedelta(minutes=59)


@pytest.mark.asyncio
async def test_retry_isolates_failures_and_records_each_outcome():
    repo = RetryRepo([(1, 29, "claude answer"), (2, 29, "grok answer")])
    persistence = Persistence()
    service = AIRunService(repo, FakeAI(), Extraction(fail_for={"claude"}), persistence)

    results = await service.retry_failed_extractions(limit=10)

    assert [(r["run_id"], r["status"]) for r in results] == [(1, "failed"), (2, "completed")]
    assert repo.extraction_updates[0][:2] == (1, "failed")
    assert "different identities" in repo.extraction_updates[0][2]
    assert repo.extraction_updates[1] == (2, "completed", None)
    assert persistence.persisted == [2]


@pytest.mark.asyncio
async def test_zero_batch_size_disables_automatic_retry(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "EXTRACTION_RETRY_BATCH_SIZE", 0)
    repo = RetryRepo([(1, 29, "x")])
    extraction = Extraction()
    service = AIRunService(repo, FakeAI(), extraction, Persistence())

    assert await service.retry_failed_extractions() == []
    assert repo.query is None
    assert extraction.calls == []


@pytest.mark.asyncio
async def test_retry_can_be_scoped_to_a_prompt_and_skip_alerts():
    repo = RetryRepo([(1, 29, "x"), (2, 30, "y")])
    service = AIRunService(repo, FakeAI(), Extraction(), Persistence())

    results = await service.retry_failed_extractions(prompt_id=29, limit=10, max_attempts=0, backoff_minutes=0, alerts=False)

    assert [r["run_id"] for r in results] == [1]
    assert repo.query["prompt_id"] == 29
    assert repo.query["max_attempts"] is None
    assert repo.query["retry_before"] is None
    assert repo.alerts == []
