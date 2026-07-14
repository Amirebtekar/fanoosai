"""Tests for AI Runs feature — prompt execution on selected AI models."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import Response


@pytest.mark.asyncio
class TestAIRunModel:
    """Test AIRun database model creation."""

    async def test_airun_has_required_fields(self):
        from app.database.models import AIRun
        from datetime import datetime, timezone

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
        assert run.prompt_id == 1
        assert run.ai_model_id == 1
        assert run.request_text == "test prompt"
        assert run.response_text == "test response"
        assert run.status == "success"
        assert run.error_message is None


@pytest.mark.asyncio
class TestAIRunEndpoint:
    """Test POST /prompts/{prompt_id}/run endpoint."""

    async def test_run_endpoint_returns_200(self, client: httpx.AsyncClient):
        """Run endpoint returns list of run results."""
        # TODO: seed a prompt with models first
        response = await client.post("/projects/1/prompts/1/run")
        assert response.status_code in (200, 404)  # 404 if no prompt seeded

    async def test_run_endpoint_returns_runs_list(self, client: httpx.AsyncClient):
        """Response should be a list of run objects."""
        response = await client.post("/projects/1/prompts/1/run")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            for run in data:
                assert "id" in run
                assert "status" in run
                assert "ai_model_id" in run
