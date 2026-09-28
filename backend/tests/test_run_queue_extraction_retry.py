import json
import time

import pytest

from app.infrastructure.run_queue import PromptRunJob, PromptRunQueue


class FakeRedis:
    def __init__(self):
        self.call = None

    async def zadd(self, key, mapping, nx=False):
        self.call = (key, mapping, nx)


@pytest.mark.asyncio
async def test_extraction_retry_queue_uses_requested_delay_and_idempotent_payload(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_000)
    redis = FakeRedis()
    queue = PromptRunQueue(redis)
    job = PromptRunJob(
        prompt_id=33,
        ai_model_id=6306,
        run_date="2026-09-28",
        source="extraction_retry",
        run_attempt=3,
        ai_run_id=1071,
    )

    await queue.enqueue_extraction_retry(job, 900)

    key, mapping, nx = redis.call
    payload, score = next(iter(mapping.items()))
    assert key == f"{queue.stream}:delayed"
    assert json.loads(payload)["run_attempt"] == 3
    assert json.loads(payload)["ai_run_id"] == 1071
    assert score == 1_900
    assert nx is True
