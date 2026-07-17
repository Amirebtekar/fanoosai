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


def test_history_list_endpoints_are_paginated_read_only_routes():
    routes = {(next(iter(route.methods)), route.path): route.response_model for route in router.routes}
    assert routes[("GET", "/brands/{brand_id}/history")] == Page
    assert routes[("GET", "/prompts/{prompt_id}/history")] == Page
    assert routes[("GET", "/prompts/{prompt_id}/latest-rankings")] == Page
    assert routes[("GET", "/projects/{project_id}/history")] == ProjectHistory
    assert routes[("GET", "/brands/{brand_id}")] == BrandDetails
    assert routes[("GET", "/prompts/{prompt_id}/brand-trends")] == PromptBrandTrends
    assert not any((route.methods - {"GET", "HEAD"}) for route in router.routes)
