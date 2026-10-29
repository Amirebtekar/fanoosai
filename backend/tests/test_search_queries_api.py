from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

import app.admin.router as admin_router
import app.analytics.router as analytics_router
from app.analytics.router import router
from app.analytics.schema import (
    ProjectSearchedSiteItem,
    ProjectSearchedSitesPage,
    ProjectSearchQueriesPage,
    ProjectSearchQueryItem,
)
from app.analytics.search_metadata import (
    normalize_query,
    run_search_queries,
    run_searched_sites,
    safe_http_url,
)

NEW = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
MID = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
OLD = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class Session:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return Rows(self.rows)

    def sql(self, index=0):
        return str(self.statements[index].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.fixture
def owned(monkeypatch):
    calls = []

    async def owned_project(project_id, session, user):
        calls.append(project_id)

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    return calls


async def queries(session, **kwargs):
    params = {"prompt_id": None, "ai_model_id": None, "page": 1, "page_size": 50, **kwargs}
    return await analytics_router.project_search_queries(10, session=session, user=SimpleNamespace(id=1), **params)


async def sites(session, **kwargs):
    params = {"prompt_id": None, "ai_model_id": None, "page": 1, "page_size": 50, **kwargs}
    return await analytics_router.project_searched_sites(10, session=session, user=SimpleNamespace(id=1), **params)


def test_schemas_and_routes():
    assert set(ProjectSearchQueryItem.model_fields) == {"query", "prompt_id", "prompt", "ai_model_id", "ai_model", "run_date", "count"}
    assert set(ProjectSearchedSiteItem.model_fields) == {
        "url", "domain", "action_type", "pattern", "prompt_id", "prompt", "ai_model_id", "ai_model", "run_date", "count",
    }
    routes = {(next(iter(route.methods)), route.path): route for route in router.routes}
    query_route = routes[("GET", "/projects/{project_id}/search-queries")]
    site_route = routes[("GET", "/projects/{project_id}/searched-sites")]
    assert query_route.response_model is ProjectSearchQueriesPage
    assert site_route.response_model is ProjectSearchedSitesPage
    for route in (query_route, site_route):
        assert {parameter.name for parameter in route.dependant.query_params} == {"prompt_id", "ai_model_id", "page", "page_size"}


def test_normalize_query_and_url_safety():
    assert normalize_query("  بهترین \n  هاست\tایران ") == "بهترین هاست ایران"
    assert normalize_query("   ") is None
    assert normalize_query(5) is None
    assert safe_http_url("https://Example.com/a?b=1") == ("https://Example.com/a?b=1", "example.com")
    assert safe_http_url("http://sub.example.org") == ("http://sub.example.org", "sub.example.org")
    for value in ("javascript:alert(1)", "ftp://example.com/x", "https://", "data:text/html,x", "/relative", None, 3, "http://[::1"):
        assert safe_http_url(value) is None


def test_run_helpers_skip_malformed_entries():
    assert run_search_queries(["A  b", "a b", 3, None, "", {"q": 1}, "c"], None) == [("a b", "A b"), ("c", "c")]
    assert run_search_queries("not-a-list", "nope") == []
    actions = [
        "junk", None, 5, {"type": "search"}, {"type": "search", "query": 7, "queries": "x"},
        {"type": "search", "query": " first "}, {"type": "search", "queries": ["Second", None, "FIRST"]},
        {"type": "open_page", "query": "ignored"},
    ]
    assert run_search_queries([], actions) == [("first", "first"), ("second", "Second")]
    assert run_search_queries([None, 4], actions) == [("first", "first"), ("second", "Second")]
    assert run_search_queries(["own"], actions) == [("own", "own")]
    assert run_searched_sites({"type": "open_page"}) == []
    assert run_searched_sites([
        {"type": "open_page", "url": "javascript:alert(1)"},
        {"type": "open_page"},
        {"type": "open_page", "url": ["https://x.example/"]},
        {"type": "search", "url": "https://x.example/"},
        {"type": "find_in_page", "url": "https://x.example/", "pattern": 5},
        {"type": "find_in_page", "url": "https://x.example/", "pattern": "  نماد  "},
        {"type": "open_page", "url": "https://x.example/", "pattern": "ignored"},
        {"type": "open_page", "url": "https://x.example/"},
    ]) == [
        ("https://x.example/", "x.example", "find_in_page", "نماد"),
        ("https://x.example/", "x.example", "open_page", None),
    ]


@pytest.mark.asyncio
async def test_search_queries_group_count_and_keep_latest_text(owned):
    session = Session([
        (1, "Prompt one", 2, "gpt", NEW, ["Best  Host", "best host", "vps"], None),
        (1, "Prompt one", 2, "gpt", MID, ["best host"], []),
        (1, "Prompt one", 3, "claude", MID, ["BEST HOST"], None),
        (4, "Prompt four", 2, "gpt", OLD, ["best host"], None),
        (1, "Prompt one", 2, "gpt", OLD, ["  best   host "], None),
    ])

    result = await queries(session)

    assert owned == [10]
    assert result.total == 4
    rows = [(item.query, item.prompt_id, item.ai_model_id, item.count, item.run_date) for item in result.items]
    assert rows == [
        ("Best Host", 1, 2, 3, NEW),
        ("vps", 1, 2, 1, NEW),
        ("BEST HOST", 1, 3, 1, MID),
        ("best host", 4, 2, 1, OLD),
    ]
    assert result.items[0].prompt == "Prompt one" and result.items[0].ai_model == "gpt"


@pytest.mark.asyncio
async def test_search_queries_latest_text_wins_even_when_rows_unordered(owned):
    session = Session([
        (1, "P", 2, "gpt", OLD, ["old text"], None),
        (1, "P", 2, "gpt", NEW, ["OLD  TEXT"], None),
    ])
    result = await queries(session)
    assert [(item.query, item.count, item.run_date) for item in result.items] == [("OLD TEXT", 2, NEW)]


@pytest.mark.asyncio
async def test_search_queries_fall_back_to_search_actions_and_skip_malformed(owned):
    session = Session([
        (1, "P", 2, "gpt", NEW, None, [{"type": "search", "queries": ["from action"]}, {"type": "open_page", "url": "https://a.example/"}]),
        (1, "P", 2, "gpt", MID, "garbage", {"type": "search", "query": "bad shape"}),
        (1, "P", 2, "gpt", OLD, [], ["junk", {"type": "search", "query": "From  Action"}]),
        (1, "P", 2, "gpt", OLD, None, None),
    ])
    result = await queries(session)
    assert [(item.query, item.count) for item in result.items] == [("from action", 2)]


@pytest.mark.asyncio
async def test_search_queries_filters_in_sql_and_pagination(owned):
    session = Session([(1, "P", 2, "gpt", datetime(2026, 10, day, tzinfo=timezone.utc), [f"q{day}"], None) for day in range(1, 6)])
    result = await queries(session, prompt_id=7, ai_model_id=3, page=2, page_size=2)

    assert result.total == 5 and result.page == 2 and result.page_size == 2
    assert [item.query for item in result.items] == ["q3", "q2"]
    sql = session.sql()
    assert "prompts.project_id = 10" in sql
    assert "ai_runs.status = 'success'" in sql
    assert "ai_runs.prompt_id = 7" in sql
    assert "ai_runs.ai_model_id = 3" in sql
    assert "ai_runs.web_search_queries IS NOT NULL OR ai_runs.web_search_actions IS NOT NULL" in sql
    assert "ORDER BY ai_runs.created_at DESC" in sql

    beyond = await queries(Session(session.rows), page=4, page_size=2)
    assert beyond.items == [] and beyond.total == 5


@pytest.mark.asyncio
async def test_search_endpoints_require_project_membership(monkeypatch):
    async def owned_project(project_id, session, user):
        raise HTTPException(404, "not found")

    monkeypatch.setattr(analytics_router, "owned_project", owned_project)
    for call in (queries, sites):
        session = Session()
        with pytest.raises(HTTPException) as error:
            await call(session)
        assert error.value.status_code == 404
        assert session.statements == []


@pytest.mark.asyncio
async def test_searched_sites_group_filter_unsafe_urls_and_count(owned):
    session = Session([
        (1, "P", 2, "gpt", NEW, [
            {"type": "open_page", "url": "https://parspack.com/blog"},
            {"type": "find_in_page", "url": "https://parspack.com/blog", "pattern": "قیمت"},
            {"type": "open_page", "url": "javascript:alert(1)"},
            {"type": "open_page", "url": "ftp://files.example/"},
            {"type": "search", "query": "x", "sources": ["https://ignored.example/"]},
            "junk",
        ]),
        (1, "P", 2, "gpt", MID, [{"type": "open_page", "url": "https://parspack.com/blog"}, {"type": "open_page", "url": "https://parspack.com/blog"}]),
        (1, "P", 3, "claude", OLD, [{"type": "open_page", "url": "https://parspack.com/blog"}]),
        (1, "P", 2, "gpt", OLD, {"type": "open_page", "url": "https://bad-shape.example/"}),
    ])

    result = await sites(session)

    assert result.total == 3
    rows = [(item.url, item.domain, item.action_type, item.pattern, item.ai_model_id, item.count, item.run_date) for item in result.items]
    assert rows == [
        ("https://parspack.com/blog", "parspack.com", "open_page", None, 2, 2, NEW),
        ("https://parspack.com/blog", "parspack.com", "find_in_page", "قیمت", 2, 1, NEW),
        ("https://parspack.com/blog", "parspack.com", "open_page", None, 3, 1, OLD),
    ]


@pytest.mark.asyncio
async def test_searched_sites_filters_in_sql_and_pagination(owned):
    session = Session([
        (1, "P", 2, "gpt", datetime(2026, 10, day, tzinfo=timezone.utc), [{"type": "open_page", "url": f"https://s{day}.example/"}])
        for day in range(1, 4)
    ])
    result = await sites(session, prompt_id=7, ai_model_id=3, page=2, page_size=2)
    assert result.total == 3
    assert [item.url for item in result.items] == ["https://s1.example/"]
    sql = session.sql()
    assert "ai_runs.prompt_id = 7" in sql and "ai_runs.ai_model_id = 3" in sql
    assert "ai_runs.web_search_actions IS NOT NULL" in sql
    assert "ai_runs.status = 'success'" in sql and "prompts.project_id = 10" in sql


def admin_rows():
    return [
        (1, "Prompt one", 2, "gpt", NEW, ["Best  Host"], None, 10, "Project ten"),
        (1, "Prompt one", 2, "gpt", MID, ["best host", "VPS price"], None, 10, "Project ten"),
        (5, "Prompt five", 2, "gpt", OLD, None, [{"type": "search", "query": "cheap vps"}], 11, "Project eleven"),
        (5, "Prompt five", 2, "gpt", OLD, "garbage", ["junk"], 11, "Project eleven"),
    ]


def test_admin_search_query_routes_require_superuser():
    routes = {route.path: route for route in admin_router.router.routes}
    for path in ("/admin/search-queries", "/admin/search-queries/export"):
        route = routes[path]
        assert route.methods == {"GET"}
        assert any(dependency.call is admin_router.require_superuser for dependency in route.dependant.dependencies)
    assert routes["/admin/search-queries"].response_model is admin_router.AdminSearchQueriesPage


@pytest.mark.asyncio
async def test_admin_search_queries_group_search_and_paginate():
    session = Session(admin_rows())
    result = await admin_router.admin_search_queries(
        project_id=None, ai_model_id=None, search="", page=1, page_size=50, session=session, _=SimpleNamespace(),
    )
    assert result.total == 3
    assert [(item.query, item.count, item.project_id, item.project_name) for item in result.items] == [
        ("Best Host", 2, 10, "Project ten"),
        ("VPS price", 1, 10, "Project ten"),
        ("cheap vps", 1, 11, "Project eleven"),
    ]

    searched = await admin_router.admin_search_queries(
        project_id=None, ai_model_id=None, search="  vPs ", page=1, page_size=1, session=Session(admin_rows()), _=SimpleNamespace(),
    )
    assert searched.total == 2
    assert [item.query for item in searched.items] == ["VPS price"]

    second = await admin_router.admin_search_queries(
        project_id=None, ai_model_id=None, search="vps", page=2, page_size=1, session=Session(admin_rows()), _=SimpleNamespace(),
    )
    assert [item.query for item in second.items] == ["cheap vps"]


@pytest.mark.asyncio
async def test_admin_search_queries_apply_filters_in_sql():
    session = Session()
    result = await admin_router.admin_search_queries(
        project_id=10, ai_model_id=3, search="", page=1, page_size=50, session=session, _=SimpleNamespace(),
    )
    assert result.total == 0 and result.items == []
    sql = session.sql()
    assert "prompts.project_id = 10" in sql
    assert "ai_runs.ai_model_id = 3" in sql
    assert "ai_runs.status = 'success'" in sql
    assert "ai_runs.web_search_queries IS NOT NULL OR ai_runs.web_search_actions IS NOT NULL" in sql


@pytest.mark.asyncio
async def test_admin_search_queries_export_csv():
    session = Session(admin_rows())
    response = await admin_router.export_admin_search_queries(
        project_id=None, ai_model_id=None, search="", session=session, _=SimpleNamespace(),
    )
    body = response.body.decode("utf-8")
    assert body.startswith("\ufeff")
    lines = body[1:].splitlines()
    assert lines[0] == "Query,Count,Project,Prompt,Model,Last run date"
    assert lines[1] == f"Best Host,2,Project ten,Prompt one,gpt,{NEW.isoformat()}"
    assert len(lines) == 4
    assert response.media_type == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == "attachment; filename=search-queries.csv"

    filtered = await admin_router.export_admin_search_queries(
        project_id=11, ai_model_id=None, search="cheap", session=Session(admin_rows()), _=SimpleNamespace(),
    )
    filtered_lines = filtered.body.decode("utf-8")[1:].splitlines()
    assert filtered_lines[1:] == [f"cheap vps,1,Project eleven,Prompt five,gpt,{OLD.isoformat()}"]
