from datetime import date
from types import SimpleNamespace

import pytest

from app.services.daily_model_run_service import DailyModelRunService


class FakeDMRRepo:
    def __init__(self, statuses):
        self.rows = {model: SimpleNamespace(model=model, status=status, attempts=1) for model, status in statuses.items()}
        self.reset_models = None

    async def ensure_rows(self, prompt_id, models, run_date):
        return list(self.rows.values())

    async def reset_for_manual(self, prompt_id, models, run_date, mode="failed"):
        self.reset_models = list(models)
        for model in models:
            row = self.rows[model]
            if mode == "all" or row.status in ("retrying", "exhausted"):
                row.status = "pending"

    async def get_runnable(self, prompt_id, run_date, now=None):
        return [row for row in self.rows.values() if row.status in ("pending", "retrying")]


def prompt():
    return SimpleNamespace(id=29, text="CDN?", models=[
        SimpleNamespace(model=SimpleNamespace(id=1, model_key="claude", is_active=True)),
        SimpleNamespace(model=SimpleNamespace(id=2, model_key="grok", is_active=True)),
        SimpleNamespace(model=SimpleNamespace(id=3, model_key="gpt", is_active=True)),
    ])


class Recorder(DailyModelRunService):
    async def _execute_models(self, prompt, runnable, run_date, mode="auto"):
        self.executed = [row.model for row in runnable]
        return self.executed


@pytest.mark.asyncio
async def test_manual_run_for_one_model_only_resets_and_runs_that_model():
    repo = FakeDMRRepo({"claude": "exhausted", "grok": "exhausted", "gpt": "success"})
    service = Recorder(repo, None, None)

    result = await service.run_manual(prompt(), run_date=date(2026, 10, 25), mode="failed", model_keys=["claude"])

    assert result == ["claude"]
    assert repo.reset_models == ["claude"]
    assert repo.rows["grok"].status == "exhausted"


@pytest.mark.asyncio
async def test_manual_run_without_model_keeps_previous_behaviour():
    repo = FakeDMRRepo({"claude": "exhausted", "grok": "retrying", "gpt": "success"})
    service = Recorder(repo, None, None)

    result = await service.run_manual(prompt(), run_date=date(2026, 10, 25), mode="failed")

    assert sorted(result) == ["claude", "grok"]


@pytest.mark.asyncio
async def test_single_model_failed_mode_does_not_rerun_a_successful_model():
    repo = FakeDMRRepo({"claude": "success", "grok": "exhausted", "gpt": "success"})
    service = Recorder(repo, None, None)

    assert await service.run_manual(prompt(), run_date=date(2026, 10, 25), mode="failed", model_keys=["claude"]) == []
