from datetime import date

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.ai_run_repository import AIRunRepository


@pytest.mark.asyncio
async def test_availability_ignores_abandoned_claims():
    class Result:
        def all(self):
            return []

    class Session:
        async def execute(self, statement):
            self.statement = statement
            return Result()

    session = Session()
    await AIRunRepository(session).get_daily_claim_sources(31, [90, 94], date(2026, 7, 30))

    sql = str(session.statement.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))
    assert "daily_prompt_runs.status = 'completed'" in sql
    assert "daily_prompt_runs.claimed_at >=" in sql
