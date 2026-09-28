from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

import app.analytics.router as analytics_router
from app.analytics.router import router
from app.analytics.schema import ModelPerformance


class Rows:
    def all(self):
        return []


class Session:
    def __init__(self):
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return Rows()


@pytest.mark.parametrize(
    ("days", "expected_start"),
    [
        (7, datetime(2026, 9, 21, tzinfo=ZoneInfo("Asia/Tehran"))),
        (30, datetime(2026, 8, 29, tzinfo=ZoneInfo("Asia/Tehran"))),
    ],
)
def test_model_performance_window_uses_tehran_calendar_days(days, expected_start):
    now = datetime(2026, 9, 27, 12, 0, tzinfo=ZoneInfo("Asia/Tehran"))

    start, end = analytics_router.model_performance_window(days, now)

    assert start == expected_start.astimezone(ZoneInfo("UTC"))
    assert end == datetime(2026, 9, 28, tzinfo=ZoneInfo("Asia/Tehran")).astimezone(ZoneInfo("UTC"))


def test_model_performance_window_rejects_unsupported_period():
    with pytest.raises(ValueError):
        analytics_router.model_performance_window(15, datetime(2026, 9, 27, tzinfo=ZoneInfo("Asia/Tehran")))


@pytest.mark.asyncio
async def test_model_performance_limits_left_join_to_period_and_counts_current_and_legacy_fallback_as_direct(monkeypatch):
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
    session = Session()

    result = await analytics_router.model_performance(
        10,
        days=7,
        session=session,
        user=SimpleNamespace(id=2),
    )

    sql = str(session.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert result == []
    assert "ai_runs.created_at >= '2026-09-20 00:00:00+00:00'" in sql
    assert "ai_runs.created_at < '2026-09-27 00:00:00+00:00'" in sql
    assert "ai_runs.provider_used IN ('avalai', '9router')" in sql
    assert "ai_runs.provider_used = 'primary'" not in sql
    assert "LEFT OUTER JOIN ai_runs" in sql


@pytest.mark.asyncio
async def test_model_performance_rejects_period_other_than_seven_or_thirty_days(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    with pytest.raises(HTTPException) as error:
        await analytics_router.model_performance(
            10,
            days=15,
            session=Session(),
            user=SimpleNamespace(id=2),
        )

    assert error.value.status_code == 422


def test_model_performance_route_has_period_parameter_and_no_fallback_field():
    route = next(route for route in router.routes if route.path == "/projects/{project_id}/model-performance")
    assert any(parameter.name == "days" for parameter in route.dependant.query_params)
    assert "fallback_successful_runs" not in ModelPerformance.model_fields
