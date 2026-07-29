"""Tests for the persisted AI-run contract."""

from datetime import datetime, timezone

from app.database.models import AIRun


def test_airun_has_required_fields():
    now = datetime.now(timezone.utc)
    run = AIRun(
        prompt_id=1,
        ai_model_id=1,
        request_text="test prompt",
        response_text="test response",
        status="success",
        created_at=now,
        completed_at=now,
    )

    assert (run.prompt_id, run.ai_model_id, run.status) == (1, 1, "success")
    assert run.error_message is None
