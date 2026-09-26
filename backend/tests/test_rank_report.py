from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

import app.analytics.router as analytics_router
from app.analytics.router import build_rank_report_rows, router
from app.analytics.schema import RankReport, RankReportRow


def test_rank_report_schemas_expose_daily_fields():
    assert set(RankReportRow.model_fields) >= {
        "prompt_id",
        "prompt",
        "ai_model_id",
        "ai_model",
        "appearances",
        "average_rank",
        "rank_change",
        "daily",
    }
    assert set(RankReport.model_fields) >= {"brand_id", "start_date", "end_date", "days", "items"}


def test_rank_report_route_is_registered_read_only():
    routes = {(next(iter(route.methods)), route.path): route.response_model for route in router.routes}
    assert routes[("GET", "/projects/{project_id}/rank-report")] == RankReport
    assert not any((route.methods - {"GET", "HEAD"}) for route in router.routes)


def test_build_rank_report_rows_aggregates_daily_averages_and_change():
    days = ["2026-07-01", "2026-07-02", "2026-07-03"]
    rows = [
        (1, "Prompt one", 7, "Model A", date(2026, 7, 1), 3.0, 2),
        (1, "Prompt one", 7, "Model A", date(2026, 7, 3), 1.0, 1),
        (2, "Prompt two", 7, "Model A", date(2026, 7, 2), 2.0, 1),
    ]

    by_prompt = {item.prompt_id: item for item in build_rank_report_rows(rows, days)}

    first = by_prompt[1]
    assert first.appearances == 3
    assert first.average_rank == 2.33
    assert first.rank_change == -2.0
    assert first.daily == {"2026-07-01": 3.0, "2026-07-03": 1.0}

    second = by_prompt[2]
    assert second.appearances == 1
    assert second.average_rank == 2.0
    assert second.rank_change is None


def test_build_rank_report_rows_keeps_single_day_observation():
    days = ["2026-07-01", "2026-07-02"]
    rows = [(1, "Prompt one", 7, "Model A", date(2026, 7, 2), 4.0, 1)]

    item = build_rank_report_rows(rows, days)[0]

    assert item.daily == {"2026-07-02": 4.0}
    assert item.rank_change is None
    assert item.average_rank == 4.0


class Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class Session:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return Rows(self.rows)


@pytest.mark.asyncio
async def test_rank_report_filters_by_brand_project_and_tehran_days(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    session = Session()

    report = await analytics_router.rank_report(
        12,
        brand_id=5,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        session=session,
        user=SimpleNamespace(id=1),
    )

    assert report.days == ["2026-07-01", "2026-07-02"]
    assert report.items == []
    sql = str(
        session.statements[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "run_brands.brand_id = 5" in sql
    assert "prompts.project_id = 12" in sql
    assert "ai_runs.created_at >=" in sql
    assert "ai_runs.created_at <" in sql
    assert "2026-06-30 20:30:00" in sql
    assert "2026-07-02 20:30:00" in sql
    assert "timezone(" in sql
    assert "AS DATE" in sql


@pytest.mark.asyncio
async def test_rank_report_rejects_invalid_date_ranges(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)

    with pytest.raises(HTTPException):
        await analytics_router.rank_report(
            12,
            brand_id=5,
            start_date=date(2026, 7, 3),
            end_date=date(2026, 7, 1),
            session=Session(),
            user=SimpleNamespace(id=1),
        )

    with pytest.raises(HTTPException):
        await analytics_router.rank_report(
            12,
            brand_id=5,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 1),
            session=Session(),
            user=SimpleNamespace(id=1),
        )
