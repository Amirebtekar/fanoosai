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
    app = (ROOT / "frontend/src/stores/auth-store.ts").read_text(encoding="utf-8")
    assert "credentials: 'include'" in api
    assert "localStorage.getItem('access_token')" not in api
    assert "localStorage.getItem('access_token')" not in app


def test_authenticated_profile_endpoint_returns_safe_user_schema():
    source = (ROOT / "backend/app/auth/router.py").read_text(encoding="utf-8")
    assert '@me_router.get("/me", response_model=UserRead)' in source
    assert "Depends(fastapi_users.current_user())" in source
    assert "hashed_password" not in source


def test_default_cors_allows_supported_local_frontend_origins():
    config = (ROOT / "backend/app/core/config.py").read_text(encoding="utf-8")
    assert "http://localhost:3000" in config
    assert "http://localhost:5173" in config
    assert "http://localhost:5174" in config


def test_sms_response_parser_accepts_provider_success_shapes():
    from app.auth.sms_service import SMSClient

    assert SMSClient._is_success_response("123456")
    assert SMSClient._is_success_response('{"recId": 123456}')
    assert SMSClient._is_success_response('{"Value": "123456", "RetStatus": 1}')
    assert not SMSClient._is_success_response("0")
    assert not SMSClient._is_success_response('{"Value": "-1", "RetStatus": 0}')
    assert not SMSClient._is_success_response("invalid response")
