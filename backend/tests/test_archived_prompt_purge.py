from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.prompt_repository import PromptRepository


class Session:
    def __init__(self):
        self.statements = []
        self.committed = False

    async def execute(self, statement):
        self.statements.append(statement)
        return type("Result", (), {"rowcount": 1})()

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_purge_removes_expired_archived_prompt_and_its_data():
    session = Session()

    removed = await PromptRepository(session).purge_archived_before(datetime(2026, 6, 24, tzinfo=timezone.utc))

    sql = "\n".join(str(statement.compile(dialect=postgresql.dialect())) for statement in session.statements)
    assert removed == 1
    assert "DELETE FROM run_brands" in sql
    assert "DELETE FROM ai_runs" in sql
    assert "DELETE FROM prompt_models" in sql
    assert "DELETE FROM daily_prompt_runs" in sql
    assert "DELETE FROM prompts" in sql
    assert session.committed
