import json
from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

import app.analytics.router as analytics_router
from app.analytics.router import router
from app.analytics.schema import CostSummary, PromptHistoryItem
from app.database.models import AIRun
from app.repositories.ai_run_repository import AIRunRepository
from app.services.ai_service import extract_response_metadata

SAMPLE_WITH_COST = {
    "output": [
        {"type": "reasoning", "encrypted_content": "gAAAA", "summary": []},
        {"type": "web_search_call", "action": {"type": "search", "queries": ["بهترین هاست ایران"], "query": "بهترین هاست ایران", "sources": None}},
        {"type": "web_search_call", "action": {"type": "open_page", "url": "https://openai.com/news/"}},
        {"type": "message", "content": [{"type": "output_text", "text": "پاسخ", "annotations": [
            {"type": "url_citation", "url": "https://parspack.com/", "title": "پارس پک", "start_index": 0, "end_index": 4},
            {"type": "url_citation", "url": "https://sibchob.ir/", "title": "سیب چوب", "start_index": 5, "end_index": 9},
        ]}]},
    ],
    "usage": {
        "input_tokens": 41234, "input_tokens_details": {"cached_tokens": 1024},
        "output_tokens": 2311, "output_tokens_details": {"reasoning_tokens": 1650}, "total_tokens": 43545,
    },
    "tool_usage": {"web_search": {"num_requests": 10}},
    "estimated_cost": {"unit": "0.3589430500", "irt": 97399.2},
}


class RecordingSession:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, item):
        self.added.append(item)

    async def execute(self, statement):
        return None

    async def commit(self):
        self.commits += 1

    async def refresh(self, item):
        return None


@pytest.mark.asyncio
async def test_create_persists_all_metadata_fields():
    session = RecordingSession()
    usage = extract_response_metadata(json.dumps(SAMPLE_WITH_COST, ensure_ascii=False))

    run = await AIRunRepository(session).create(
        prompt_id=1, ai_model_id=2, request_text="q", response_text="{}", status="success", provider_used="primary", usage=usage,
    )

    assert session.added == [run] and isinstance(run, AIRun)
    assert (run.prompt_tokens, run.completion_tokens, run.total_tokens) == (41234, 2311, 43545)
    assert (run.reasoning_tokens, run.cached_tokens, run.web_search_count) == (1650, 1024, 10)
    assert run.cost_irt == 97399.2
    assert run.cost_usd == pytest.approx(0.35894305)
    assert run.web_search_queries == usage["web_search_queries"]
    assert run.web_search_actions == usage["web_search_actions"]
    assert run.citations == [{"url": "https://parspack.com/", "title": "پارس پک"}, {"url": "https://sibchob.ir/", "title": "سیب چوب"}]


@pytest.mark.asyncio
async def test_create_coerces_legacy_and_invalid_usage_values():
    session = RecordingSession()
    run = await AIRunRepository(session).create(
        prompt_id=1, ai_model_id=2, request_text="q", status="success",
        usage={"prompt_tokens": "12", "total_tokens": 20.0, "cost_irt": "0.3589430500", "cost_usd": "nan",
               "web_search_count": True, "web_search_queries": "not-a-list", "citations": None},
    )
    assert run.prompt_tokens == 12 and run.total_tokens == 20
    assert run.cost_irt == pytest.approx(0.35894305)
    assert run.cost_usd is None and run.web_search_count is None
    assert run.web_search_queries is None and run.citations is None and run.web_search_actions is None

    failed = await AIRunRepository(session).create(prompt_id=1, ai_model_id=2, request_text="q", usage=None)
    assert failed.cost_irt is None and failed.web_search_queries is None and failed.status == "failed"


def test_prompt_history_item_exposes_metadata():
    fields = set(PromptHistoryItem.model_fields)
    assert fields >= {
        "prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "cached_tokens", "cost_irt", "cost_usd",
        "web_search_count", "web_search_queries", "web_search_actions", "citations",
    }


@pytest.mark.asyncio
async def test_prompt_history_selects_and_returns_metadata(monkeypatch):
    async def owned_prompt(prompt_id, session, user):
        return SimpleNamespace(project_id=9)

    run_date = datetime(2026, 10, 30, tzinfo=timezone.utc)
    row = (
        5, "gpt", run_date, "q", "{}", "success", "completed", 2,
        100, 20, 120, 10, None, 950.5, 0.0035, 3, ["q1"], [{"type": "open_page", "url": "https://a.example/"}, "junk"],
        [{"url": "https://a.example/", "title": None}],
    )
    old_row = (6, "gpt", run_date, "q", "{}", "success", "completed", 0, *([None] * 11))

    class Rows:
        def all(self):
            return [row, old_row]

    class Session:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return Rows()

        async def scalar(self, statement):
            return 2

    monkeypatch.setattr(analytics_router, "owned_prompt", owned_prompt)
    session = Session()
    page = await analytics_router.prompt_history(3, ai_model_id=None, start_date=None, end_date=None, page=1, page_size=20, session=session, user=SimpleNamespace(id=1))

    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    flat = " ".join(sql.split())
    from_clause = flat.split(" FROM ", 1)[1].split(" WHERE ", 1)[0]
    assert "JOIN prompts ON prompts.id = ai_runs.prompt_id" in from_clause
    assert ", prompts" not in from_clause
    for column in ("cost_irt", "cost_usd", "web_search_queries", "web_search_actions", "citations", "reasoning_tokens", "cached_tokens"):
        assert f"ai_runs.{column}" in sql
    first, second = page.items
    assert first.cost_irt == 950.5 and first.total_tokens == 120 and first.web_search_count == 3
    assert first.web_search_queries == ["q1"]
    assert first.web_search_actions == [{"type": "open_page", "url": "https://a.example/"}]
    assert first.citations == [{"url": "https://a.example/", "title": None}]
    assert second.cost_irt is None and second.web_search_queries is None and second.citations is None
    assert second.brands_count == 0


class CostRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class CostSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return CostRows(self.rows)


@pytest.mark.asyncio
async def test_cost_summary_totals_and_orders_models_by_cost(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    monkeypatch.setattr(analytics_router, "model_performance_window", lambda days: (
        datetime(2026, 10, 24, tzinfo=ZoneInfo("UTC")), datetime(2026, 10, 31, tzinfo=ZoneInfo("UTC")),
    ))
    session = CostSession([
        ("cheap", 10, 4, 1000.0, 0.004, 5000, 6),
        ("pricey", 3, 3, 97399.2, 0.35894305, 43545, 10),
        ("legacy", 7, 0, 0, 0, 0, 0),
    ])

    result = await analytics_router.cost_summary(10, days=7, session=session, user=SimpleNamespace(id=4))

    assert isinstance(result, CostSummary)
    assert result.total_cost_irt == 98399.2
    assert result.total_cost_usd == pytest.approx(0.362943, abs=1e-6)
    assert (result.runs_with_cost, result.total_runs, result.total_tokens, result.web_search_count) == (7, 20, 48545, 16)
    assert [item.ai_model for item in result.models] == ["pricey", "cheap", "legacy"]
    assert result.models[0].cost_irt == 97399.2 and result.models[0].runs == 3
    sql = str(session.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "prompts.project_id = 10" in sql
    assert "ai_runs.status = 'success'" in sql
    assert "ai_runs.created_at >= '2026-10-24 00:00:00+00:00'" in sql
    assert "ai_runs.created_at < '2026-10-31 00:00:00+00:00'" in sql
    assert "sum(ai_runs.cost_irt)" in sql
    assert "ai_runs.cost_irt IS NOT NULL" in sql


@pytest.mark.asyncio
async def test_cost_summary_empty_and_invalid_period(monkeypatch):
    async def owned_project(project_id, session, user):
        return None

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    empty = await analytics_router.cost_summary(10, days=30, session=CostSession([]), user=SimpleNamespace(id=4))
    assert empty.model_dump() == {
        "days": 30, "total_cost_irt": 0.0, "total_cost_usd": 0.0, "runs_with_cost": 0, "total_runs": 0,
        "total_tokens": 0, "web_search_count": 0, "models": [],
    }
    with pytest.raises(HTTPException) as error:
        await analytics_router.cost_summary(10, days=15, session=CostSession([]), user=SimpleNamespace(id=4))
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_cost_summary_requires_project_membership(monkeypatch):
    async def owned_project(project_id, session, user):
        raise HTTPException(404, "not found")

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    with pytest.raises(HTTPException) as error:
        await analytics_router.cost_summary(10, days=7, session=CostSession([]), user=SimpleNamespace(id=4))
    assert error.value.status_code == 404


def test_cost_summary_route_is_registered():
    route = next(route for route in router.routes if route.path == "/projects/{project_id}/cost-summary")
    assert route.methods == {"GET"}
    assert route.response_model is CostSummary
    assert {parameter.name for parameter in route.dependant.query_params} == {"days"}
