from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

import app.analytics.router as analytics_router
from app.analytics.router import build_prompt_leaders, prompt_leader_threshold, router


def row(prompt_id, brand_id, name, domain, appearances, avg_rank, prompt="p"):
    return (prompt_id, prompt, brand_id, name, domain, appearances, avg_rank)


@pytest.mark.parametrize("total,threshold", [(0, 2), (1, 2), (5, 2), (10, 2), (11, 3), (32, 7), (35, 7), (36, 8)])
def test_threshold_is_twenty_percent_with_minimum_of_two(total, threshold):
    assert prompt_leader_threshold(total) == threshold


def test_rare_brand_with_best_rank_is_not_leader():
    items = build_prompt_leaders(
        [
            row(1, 10, "rare", "rare.ir", 6, 1.0),
            row(1, 11, "arvan", "arvancloud.ir", 30, 1.2),
            row(1, 12, "parspack", "parspack.com", 28, 3.5),
        ],
        {1: 32}, set(), {"parspack.com"},
    )
    item = items[0]
    assert item.total_runs == 32
    assert item.leader.brand == "arvan"
    assert item.own.brand == "parspack" and item.own.position == 2 and item.own.eligible
    assert not item.own_is_leader


def test_falls_back_to_all_brands_when_none_is_eligible():
    items = build_prompt_leaders(
        [row(1, 10, "a", "a.ir", 1, 3.0), row(1, 11, "b", "b.ir", 1, 2.0)],
        {1: 20}, set(), set(),
    )
    assert items[0].leader.brand == "b"
    assert items[0].own is None and not items[0].own_is_leader


def test_own_brand_not_eligible_has_no_position():
    items = build_prompt_leaders(
        [row(1, 10, "leader", "l.ir", 10, 2.0), row(1, 11, "me", "me.ir", 1, 1.0)],
        {1: 10}, {11}, set(),
    )
    own = items[0].own
    assert items[0].leader.brand == "leader"
    assert own.brand_id == 11 and own.position is None and own.eligible is False
    assert own.appearances == 1


def test_own_brand_leads_and_matches_by_normalized_domain():
    items = build_prompt_leaders(
        [row(1, 10, "me", "ParsPack.com.", 10, 1.4), row(1, 11, "other", "o.ir", 10, 2.0)],
        {1: 10}, set(), {"parspack.com"},
    )
    assert items[0].own_is_leader and items[0].own.position == 1


def test_ties_break_on_appearances_then_name():
    items = build_prompt_leaders(
        [row(1, 1, "b", "b.ir", 5, 2.0), row(1, 2, "a", "a.ir", 5, 2.0), row(1, 3, "c", "c.ir", 8, 2.0)],
        {1: 10}, set(), set(),
    )
    assert items[0].leader.brand == "c"
    items = build_prompt_leaders(
        [row(1, 1, "b", "b.ir", 5, 2.0), row(1, 2, "a", "a.ir", 5, 2.0)],
        {1: 10}, set(), set(),
    )
    assert items[0].leader.brand == "a"


def test_total_never_below_appearances_and_prompts_sorted_by_need():
    rows = [
        row(1, 1, "me", "me.ir", 9, 1.0, prompt="leading"),
        row(2, 2, "x", "x.ir", 9, 1.0, prompt="missing"),
        row(3, 2, "x", "x.ir", 9, 1.0, prompt="second"),
        row(3, 1, "me", "me.ir", 9, 2.0, prompt="second"),
        row(4, 2, "x", "x.ir", 9, 1.0, prompt="third"),
        row(4, 3, "y", "y.ir", 9, 2.0, prompt="third"),
        row(4, 1, "me", "me.ir", 9, 3.0, prompt="third"),
        row(5, 2, "x", "x.ir", 9, 1.0, prompt="rare"),
        row(5, 1, "me", "me.ir", 1, 1.0, prompt="rare"),
    ]
    items = build_prompt_leaders(rows, {1: 9, 2: 3}, {1}, set())
    assert [item.prompt for item in items] == ["missing", "rare", "third", "second", "leading"]
    assert items[0].total_runs == 9
    assert [item.own_is_leader for item in items] == [False, False, False, False, True]


def test_empty_rows_return_no_items():
    assert build_prompt_leaders([], {}, set(), set()) == []


class Result:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class Session:
    def __init__(self, totals, rows, owned):
        self.responses = [Result(totals), Result(rows), Result(owned)]
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self.responses.pop(0)


def compile_sql(statement):
    return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.mark.asyncio
async def test_endpoint_filters_project_window_and_prompt(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    monkeypatch.setattr(analytics_router, "model_performance_window", lambda days: (
        datetime(2026, 10, 22, tzinfo=ZoneInfo("UTC")), datetime(2026, 10, 29, tzinfo=ZoneInfo("UTC")),
    ))
    session = Session(
        [(29, 32)],
        [row(29, 1, "ابرآروان", "arvancloud.ir", 30, 1.1, "CDN"), row(29, 2, "پارس‌پک", "parspack.com", 25, 3.2, "CDN")],
        [(None, "ParsPack.com")],
    )

    result = await analytics_router.prompt_leaders(10, days=7, prompt_id=29, session=session, user=SimpleNamespace(id=1))

    assert result.days == 7 and result.has_own_brand
    assert result.items[0].leader.brand == "ابرآروان"
    assert result.items[0].own.position == 2 and not result.items[0].own_is_leader
    for statement in session.statements[:2]:
        sql = compile_sql(statement)
        assert "prompts.project_id = 10" in sql
        assert "ai_runs.status = 'success'" in sql
        assert "prompts.id = 29" in sql
        assert "ai_runs.created_at >= '2026-10-22 00:00:00+00:00'" in sql
        assert "ai_runs.created_at < '2026-10-29 00:00:00+00:00'" in sql
    assert "count(DISTINCT run_brands.ai_run_id)" in compile_sql(session.statements[1])
    owned_sql = compile_sql(session.statements[2])
    assert "project_brands.project_id = 10" in owned_sql and "project_brands.kind = 'owned'" in owned_sql


@pytest.mark.asyncio
async def test_endpoint_without_prompt_filter_and_own_brand(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    session = Session([], [], [])
    result = await analytics_router.prompt_leaders(10, days=30, prompt_id=None, session=session, user=SimpleNamespace(id=1))
    assert result.items == [] and result.has_own_brand is False and result.days == 30
    for statement in session.statements[:2]:
        where = compile_sql(statement).split("WHERE", 1)[1]
        assert "prompts.id = " not in where and "prompts.project_id = 10" in where


@pytest.mark.asyncio
async def test_endpoint_rejects_unsupported_period(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    with pytest.raises(HTTPException) as error:
        await analytics_router.prompt_leaders(10, days=14, prompt_id=None, session=None, user=SimpleNamespace(id=1))
    assert error.value.status_code == 422


def test_route_is_registered():
    route = next(route for route in router.routes if route.path == "/projects/{project_id}/prompt-leaders")
    assert route.response_model.__name__ == "PromptLeaders"
    assert {parameter.name for parameter in route.dependant.query_params} >= {"days", "prompt_id"}
