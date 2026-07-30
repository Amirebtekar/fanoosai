import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

import app.analytics.router as analytics_router
from app.analytics.schema import (
    BrandDetails,
    BrandHistoryItem,
    LatestRanking,
    BrandTrend,
    BrandTrendPoint,
    PromptBrandTrends,
    Page,
    ProjectHistory,
    PromptHistoryItem,
    ModelPerformance,
    ProjectReferenceItem,
    ProjectReferencesPage,
)
from app.analytics.router import router


def test_history_schemas_expose_dashboard_fields():
    assert set(BrandHistoryItem.model_fields) >= {"date", "rank", "ai_model", "prompt", "ai_run_id"}
    assert set(PromptHistoryItem.model_fields) >= {"ai_run_id", "ai_model", "run_date", "status", "extraction_status", "brands_count"}
    assert set(ProjectHistory.model_fields) >= {"total_runs", "successful_runs", "failed_runs", "brands_count", "last_successful_run"}
    assert set(LatestRanking.model_fields) >= {"brand", "domain", "rank", "confidence", "ai_model", "run_date"}
    assert set(BrandDetails.model_fields) >= {"name", "domain", "total_appearances", "average_rank", "best_rank", "worst_rank", "first_seen", "last_seen"}
    assert set(BrandTrendPoint.model_fields) >= {"date", "rank", "ai_run_id"}
    assert set(BrandTrend.model_fields) >= {"brand_id", "brand", "domain", "ai_model_id", "ai_model", "points", "rank_change", "trend"}
    assert set(PromptBrandTrends.model_fields) >= {"prompt_id", "items"}
    assert set(ModelPerformance.model_fields) >= {
        "ai_model",
        "total_runs",
        "direct_successful_runs",
        "fallback_successful_runs",
        "failed_runs",
        "success_rate",
    }
    assert set(ProjectReferenceItem.model_fields) == {
        "url",
        "prompt_id",
        "prompt",
        "ai_model_id",
        "ai_model",
        "run_date",
    }


def test_history_list_endpoints_are_paginated_read_only_routes():
    routes = {(next(iter(route.methods)), route.path): route.response_model for route in router.routes}
    assert routes[("GET", "/brands/{brand_id}/history")] == Page
    assert routes[("GET", "/prompts/{prompt_id}/history")] == Page
    assert routes[("GET", "/prompts/{prompt_id}/latest-rankings")] == Page
    assert routes[("GET", "/projects/{project_id}/history")] == ProjectHistory
    assert routes[("GET", "/brands/{brand_id}")] == BrandDetails
    assert routes[("GET", "/prompts/{prompt_id}/brand-trends")] == PromptBrandTrends
    assert routes[("GET", "/projects/{project_id}/model-performance")] == list[ModelPerformance]
    assert routes[("GET", "/projects/{project_id}/references")] == ProjectReferencesPage
    assert not any((route.methods - {"GET", "HEAD"}) for route in router.routes)


@pytest.mark.asyncio
async def test_project_references_cover_all_prompts_and_deduplicate_per_model(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    class Rows:
        def all(self):
            return [
                (
                    1,
                    "Prompt one",
                    2,
                    "Model two",
                    datetime(2026, 7, 31, tzinfo=timezone.utc),
                    json.dumps({
                        "sources": [
                            "https://example.com/one",
                            "https://example.org/two",
                            "javascript:alert(1)",
                        ],
                    }),
                ),
                (
                    1,
                    "Prompt one",
                    2,
                    "Model two",
                    datetime(2026, 7, 30, tzinfo=timezone.utc),
                    json.dumps({"sources": ["https://example.com/one"]}),
                ),
                (
                    3,
                    "Prompt three",
                    4,
                    "Model four",
                    datetime(2026, 7, 29, tzinfo=timezone.utc),
                    json.dumps({"sources": ["https://example.com/one"]}),
                ),
            ]

    class Session:
        async def execute(self, statement):
            return Rows()

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)

    result = await analytics_router.project_references(
        9,
        prompt_id=None,
        ai_model_id=None,
        page=1,
        page_size=2,
        session=Session(),
        user=SimpleNamespace(id=1),
    )

    assert result.total == 3
    assert [item.url for item in result.items] == [
        "https://example.com/one",
        "https://example.org/two",
    ]
    assert result.items[0].prompt_id == 1
    assert result.items[0].ai_model_id == 2


@pytest.mark.asyncio
async def test_project_references_apply_prompt_and_model_filters(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    class Rows:
        def all(self):
            return []

    class Session:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return Rows()

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    session = Session()
    await analytics_router.project_references(
        9,
        prompt_id=7,
        ai_model_id=3,
        page=1,
        page_size=50,
        session=session,
        user=SimpleNamespace(id=1),
    )

    sql = str(session.statement.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))
    assert "ai_runs.prompt_id = 7" in sql
    assert "ai_runs.ai_model_id = 3" in sql


@pytest.mark.asyncio
async def test_prompt_history_total_uses_the_same_filters(monkeypatch):
    async def owned_prompt(prompt_id, session, user):
        return SimpleNamespace(project_id=9)

    class Rows:
        def all(self):
            return []

    class Session:
        def __init__(self):
            self.count_statement = None

        async def execute(self, statement):
            return Rows()

        async def scalar(self, statement):
            self.count_statement = statement
            return 0

    monkeypatch.setattr(analytics_router, "owned_prompt", owned_prompt)
    session = Session()
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    end = datetime(2026, 7, 2, tzinfo=timezone.utc)

    await analytics_router.prompt_history(
        3,
        ai_model_id=4,
        start_date=start,
        end_date=end,
        page=1,
        page_size=20,
        session=session,
        user=SimpleNamespace(id=1),
    )

    sql = str(
        session.count_statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "ai_runs.ai_model_id = 4" in sql
    assert "ai_runs.created_at >=" in sql
    assert "ai_runs.created_at <=" in sql


@pytest.mark.asyncio
async def test_dashboard_brand_metrics_are_project_scoped(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    class Result:
        def __init__(self, one=None):
            self._one = one

        def one(self):
            return self._one

        def all(self):
            return []

    class Session:
        def __init__(self):
            self.statements = []

        async def scalar(self, statement):
            return 0

        async def execute(self, statement):
            self.statements.append(statement)
            return Result((0, 0, 0, 0, 0, None)) if len(self.statements) == 1 else Result()

    session = Session()
    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    await analytics_router.dashboard(9, session=session, user=SimpleNamespace(id=1))

    sql = str(
        session.statements[1].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "prompts.project_id = 9" in sql


def test_visibility_is_percentage_of_successful_runs_with_owned_brand():
    assert analytics_router.visibility_percent(owned_runs=3, successful_runs=4) == 75.0
    assert analytics_router.visibility_percent(owned_runs=0, successful_runs=0) == 0.0
