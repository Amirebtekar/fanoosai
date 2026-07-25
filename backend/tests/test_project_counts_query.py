import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.project_repository import ProjectRepository


class Session:
    async def execute(self, statement):
        self.statement = statement

        class Result:
            def all(self): return []

        return Result()


@pytest.mark.asyncio
async def test_project_counts_only_include_active_prompts():
    session = Session()

    await ProjectRepository(session).list_by_user(1)

    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "prompts.is_active IS true" in sql
