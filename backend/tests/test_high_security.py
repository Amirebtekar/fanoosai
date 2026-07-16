from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_ai_gateway_management_routes_are_not_public():
    source = (ROOT / "backend/app/projects/ai_models_router.py").read_text(encoding="utf-8")
    assert "current_user(active=True, superuser=True)" in source


def test_analytics_queries_enforce_resource_ownership():
    analytics = (ROOT / "backend/app/analytics/router.py").read_text(encoding="utf-8")
    extra = (ROOT / "backend/app/analytics/extra_router.py").read_text(encoding="utf-8")
    assert "await owned_prompt(prompt_id, session, user)" in analytics
    assert "project_id=prompt.project_id" in analytics
    assert "await owned_brand(brand_id, session, user)" in extra
    assert "Project.user_id == user.id" in extra


def test_frontend_uses_http_only_cookie_auth_contract():
    api = (ROOT / "frontend/src/lib/api.ts").read_text(encoding="utf-8")
    app = (ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    assert "credentials: 'include'" in api
    assert "localStorage.getItem('access_token')" not in api
    assert "localStorage.getItem('access_token')" not in app
