from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

import app.analytics.router as analytics_router
from app.analytics.router import router
from app.analytics.schema import BrandRankSummaryItem


class Rows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values

    def scalar_one(self):
        return len(self.values)


class Session:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.statement = None

    async def scalar(self, statement):
        self.count_statement = statement
        return len(self.rows)

    async def execute(self, statement):
        self.statement = statement
        return Rows(self.rows)


@pytest.mark.asyncio
async def test_brand_rank_summary_averages_all_models_and_limits_to_tehran_window(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    monkeypatch.setattr(
        analytics_router,
        "model_performance_window",
        lambda days: (
            datetime(2026, 9, 20, tzinfo=ZoneInfo("UTC")),
            datetime(2026, 9, 27, tzinfo=ZoneInfo("UTC")),
        ),
    )
    session = Session([
        (33, "هاست ایرانی ارزان از کجا بگیرم؟", 1, "پارس‌پک", "parspack.com", 1.5, 4),
        (33, "هاست ایرانی ارزان از کجا بگیرم؟", 6, "ایران‌سرور", "iranserver.com", 2.0, 3),
    ])

    result = await analytics_router.brand_rank_summary(
        10,
        days=7,
        prompt_id=33,
        brand_id=1,
        page=1,
        page_size=20,
        session=session,
        user=SimpleNamespace(id=4),
    )

    sql = str(session.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert result.total == 2
    assert result.items[0] == BrandRankSummaryItem(
        prompt_id=33,
        prompt="هاست ایرانی ارزان از کجا بگیرم؟",
        brand_id=1,
        brand="پارس‌پک",
        domain="parspack.com",
        average_rank=1.5,
        observations=4,
    )
    assert "prompts.project_id = 10" in sql
    assert "prompts.id = 33" in sql
    assert "brands.id = 1" in sql
    count_sql = str(session.count_statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "brands.id = 1" in count_sql
    assert "ai_runs.status = 'success'" in sql
    assert "ai_runs.created_at >= '2026-09-20 00:00:00+00:00'" in sql
    assert "ai_runs.created_at < '2026-09-27 00:00:00+00:00'" in sql
    assert "GROUP BY prompts.id, prompts.text, brands.id, brands.name, brands.domain" in sql
    assert "ai_runs.ai_model_id =" not in sql


@pytest.mark.asyncio
async def test_brand_rank_summary_rejects_unsupported_period(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    with pytest.raises(HTTPException) as error:
        await analytics_router.brand_rank_summary(
            10,
            days=15,
            prompt_id=None,
            page=1,
            page_size=20,
            session=Session(),
            user=SimpleNamespace(id=4),
        )
    assert error.value.status_code == 422


def test_brand_rank_summary_route_is_paginated():
    route = next(route for route in router.routes if route.path == "/projects/{project_id}/brand-rank-summary")
    assert route.response_model.__name__ == "Page"
    assert {parameter.name for parameter in route.dependant.query_params} >= {"days", "prompt_id", "brand_id", "page", "page_size"}
