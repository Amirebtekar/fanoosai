from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

import app.analytics.router as analytics_router


class Session:
    def __init__(self, rows=None):
        self.rows = rows or []

    async def execute(self, statement):
        self.statement = statement
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: self.rows))


@pytest.mark.asyncio
async def test_brand_trends_query_points_from_oldest_to_newest(monkeypatch):
    async def owned_prompt(*_):
        return SimpleNamespace(id=19, project_id=5)

    monkeypatch.setattr(analytics_router, "owned_prompt", owned_prompt)
    session = Session()

    await analytics_router.prompt_brand_trends(
        19,
        ai_model_id=None,
        brand_ids=None,
        start_date=datetime(2026, 7, 20, tzinfo=timezone.utc),
        end_date=None,
        session=session,
        user=SimpleNamespace(),
    )

    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY anon_1.brand_id, anon_1.ai_model_id, anon_1.date ASC" in sql


@pytest.mark.asyncio
async def test_brand_trends_merge_spaced_name_variants(monkeypatch):
    async def owned_prompt(*_):
        return SimpleNamespace(id=19, project_id=5)

    monkeypatch.setattr(analytics_router, "owned_prompt", owned_prompt)
    session = Session([
        {"brand_id": 1, "brand": "پارس‌پک", "domain": "parspack.com", "ai_model_id": 2, "ai_model": "Gemini", "rank": 2, "ai_run_id": 10, "date": datetime(2026, 7, 28, tzinfo=timezone.utc), "point_rank": 2},
        {"brand_id": 150, "brand": "پارسپک", "domain": "parspak.com", "ai_model_id": 2, "ai_model": "Gemini", "rank": 2, "ai_run_id": 11, "date": datetime(2026, 7, 29, tzinfo=timezone.utc), "point_rank": 1},
    ])

    result = await analytics_router.prompt_brand_trends(
        19, ai_model_id=None, brand_ids=None, start_date=None, end_date=None,
        session=session, user=SimpleNamespace(),
    )

    assert len(result.items) == 1
    assert [point.rank for point in result.items[0].points] == [2, 2]
