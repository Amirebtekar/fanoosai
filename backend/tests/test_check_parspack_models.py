import pytest

from check_parspack_models import format_report, model_ids


def test_report_shows_model_status_latency_and_summary():
    report = format_report([
        {"model": "model/ok", "active": True, "status": 200, "seconds": 1.23, "detail": "OK"},
        {"model": "model/down", "active": False, "status": 503, "seconds": 2.0, "detail": "unavailable"},
    ])

    assert "| model/ok | YES | 200 | 1.23 | OK |" in report
    assert "| model/down | NO | 503 | 2.00 | unavailable |" in report
    assert "**Summary:** 1/2 models responded successfully." in report


def test_empty_model_listing_is_rejected():
    with pytest.raises(ValueError, match="returned no models"):
        model_ids({"data": []})
