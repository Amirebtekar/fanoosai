from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

import app.analytics.router as analytics_router
from app.analytics.router import build_competitor_radar, rank_score, router


def row(brand_id, name, domain, appearances, avg_rank, first, models, prompts):
    return (brand_id, name, domain, appearances, avg_rank, first, models, prompts)


def test_rank_score_maps_rank_one_to_full_and_ten_to_zero():
    assert rank_score(1) == 100.0
    assert rank_score(10) == 0.0
    assert rank_score(14) == 0.0
    assert rank_score(5.5) == 50.0
    assert rank_score(None) == 0.0


def test_axes_are_percentages_and_strength_is_weighted():
    radar = build_competitor_radar(
        [row(1, "ابرآروان", "arvancloud.cloud", 32, 1.0, 32, 5, 2)],
        total_runs=32, total_models=5, total_prompts=2,
        owned_domains=set(), owned_brand_ids=set(), limit=6, days=7,
    )
    brand = radar.brands[0]
    assert (brand.visibility, brand.rank_score, brand.top_three, brand.model_coverage, brand.prompt_coverage) == (100.0, 100.0, 100.0, 100.0, 100.0)
    assert brand.strength == 100.0
    assert brand.appearances == 32 and brand.top_three_count == 32


def test_strongest_competitors_first_and_own_brand_always_included():
    rows = [
        row(1, "پارس‌پک", "parspack.com", 3, 6.0, 0, 1, 1),
        row(2, "ابرآروان", "arvancloud.cloud", 30, 1.1, 27, 5, 2),
        row(3, "ابر دراک", "derak.cloud", 14, 2.1, 2, 4, 1),
        row(4, "سرور تک", "x.ir", 1, 4.0, 0, 1, 1),
    ]
    radar = build_competitor_radar(
        rows, total_runs=32, total_models=5, total_prompts=2,
        owned_domains={"parspack.com"}, owned_brand_ids=set(), limit=3, days=30,
    )
    names = [brand.brand for brand in radar.brands]
    assert names == ["ابرآروان", "ابر دراک", "پارس‌پک"]
    assert [brand.is_owned for brand in radar.brands] == [False, False, True]
    assert radar.brands[0].strength > radar.brands[1].strength > radar.brands[2].strength


def test_own_brand_matched_by_id_and_not_duplicated_when_also_strong():
    rows = [row(1, "پارس‌پک", "parspack.com", 30, 1.5, 10, 5, 2), row(2, "a", "a.ir", 5, 3.0, 0, 2, 1)]
    radar = build_competitor_radar(
        rows, total_runs=32, total_models=5, total_prompts=2,
        owned_domains=set(), owned_brand_ids={1}, limit=6, days=7,
    )
    assert [brand.brand_id for brand in radar.brands] == [1, 2]
    assert sum(brand.is_owned for brand in radar.brands) == 1


def test_rank_axes_are_discounted_for_brands_with_few_answers():
    """A brand seen in 5 of 1000 answers must not outrank one seen in 600."""
    rows = [
        row(1, "rare", "rare.com", 5, 1.2, 4, 5, 2),
        row(2, "steady", "steady.ir", 600, 2.5, 200, 6, 10),
    ]
    radar = build_competitor_radar(
        rows, total_runs=1000, total_models=6, total_prompts=10,
        owned_domains=set(), owned_brand_ids=set(), limit=6, days=30,
    )
    rare = next(b for b in radar.brands if b.brand == "rare")
    steady = next(b for b in radar.brands if b.brand == "steady")
    assert rare.rank_score == round(rank_score(1.2) * 5 / 50, 1)
    assert rare.top_three == 80.0
    assert rare.top_three_count == 4
    assert steady.rank_score == rank_score(2.5)
    assert [b.brand for b in radar.brands] == ["steady", "rare"]


def test_small_windows_use_minimum_sample_of_five():
    radar = build_competitor_radar(
        [row(1, "a", "a.ir", 5, 1.0, 5, 1, 1)], total_runs=32, total_models=5, total_prompts=1,
        owned_domains=set(), owned_brand_ids=set(), limit=6, days=7,
    )
    assert radar.brands[0].rank_score == 100.0 and radar.brands[0].top_three == 100.0


def test_empty_window_returns_no_brands_and_zero_totals():
    radar = build_competitor_radar([], total_runs=0, total_models=0, total_prompts=0, owned_domains=set(), owned_brand_ids=set(), limit=6, days=7)
    assert radar.brands == [] and radar.total_runs == 0


@pytest.mark.parametrize("appearances,count,score", [(10, 8, 80.0), (3, 1, 33.3), (5, 5, 100.0), (5, 0, 0.0), (0, 0, 0.0), (0, None, 0.0)])
def test_top_three_uses_brand_appearances_without_confidence_discount(appearances, count, score):
    radar = build_competitor_radar(
        [row(1, "a", "a.ir", appearances, None, count, 0, 0)],
        total_runs=1000, total_models=0, total_prompts=0,
        owned_domains=set(), owned_brand_ids=set(), limit=6, days=7,
    )
    brand = radar.brands[0]
    assert brand.top_three == score
    assert brand.top_three_count == (count or 0)
    assert brand.strength == round(brand.visibility * 0.35 + score * 0.15, 1)
    assert brand.rank_score == 0.0
    assert "growth" not in brand.model_dump()


def test_top_three_has_fifteen_percent_weight():
    radar = build_competitor_radar(
        [row(1, "a", "a.ir", 10, 2.0, 0, 1, 1), row(2, "b", "b.ir", 10, 2.0, 10, 1, 1)],
        total_runs=20, total_models=1, total_prompts=1,
        owned_domains=set(), owned_brand_ids=set(), limit=6, days=7,
    )
    assert radar.brands[0].brand_id == 2
    assert radar.brands[0].strength - radar.brands[1].strength == 15.0


class Result:
    def __init__(self, values):
        self.values = values

    def one(self):
        return self.values

    def all(self):
        return self.values


class Session:
    def __init__(self, totals, rows, owned):
        self.responses = [Result(totals), Result(rows), Result(owned)]
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_endpoint_filters_project_window_and_prompt(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    monkeypatch.setattr(analytics_router, "model_performance_window", lambda days: (
        datetime(2026, 10, 22, tzinfo=ZoneInfo("UTC")), datetime(2026, 10, 29, tzinfo=ZoneInfo("UTC")),
    ))
    session = Session((32, 5, 1), [row(1, "پارس‌پک", "parspack.com", 30, 3.27, 18, 5, 1)], [(None, "ParsPack.com")])

    radar = await analytics_router.competitor_radar(10, days=7, prompt_id=29, limit=6, session=session, user=SimpleNamespace(id=1))

    assert radar.total_runs == 32 and radar.brands[0].is_owned
    assert radar.brands[0].top_three_count == 18
    assert radar.brands[0].top_three == 60.0
    brand_sql = str(session.statements[1].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "count(DISTINCT run_brands.ai_run_id) FILTER (WHERE run_brands.rank <= 3)" in brand_sql
    assert "run_brands.rank = 1" not in brand_sql
    for statement in session.statements[:2]:
        sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        assert "prompts.project_id = 10" in sql
        assert "ai_runs.status = 'success'" in sql
        assert "prompts.id = 29" in sql
        assert "ai_runs.created_at >= '2026-10-22 00:00:00+00:00'" in sql
        assert "ai_runs.created_at < '2026-10-29 00:00:00+00:00'" in sql
        assert "2026-10-25" not in sql


@pytest.mark.asyncio
async def test_endpoint_rejects_unsupported_period(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    with pytest.raises(HTTPException) as error:
        await analytics_router.competitor_radar(10, days=15, prompt_id=None, limit=6, session=None, user=SimpleNamespace(id=1))
    assert error.value.status_code == 422


def test_route_is_registered():
    route = next(route for route in router.routes if route.path == "/projects/{project_id}/competitor-radar")
    assert {parameter.name for parameter in route.dependant.query_params} >= {"days", "prompt_id", "limit"}
