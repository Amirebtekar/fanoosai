from types import SimpleNamespace

import pytest

from app.projects import prompt_router
from app.repositories.project_repository import ProjectRepository


@pytest.mark.asyncio
async def test_run_route_can_target_one_model(monkeypatch):
    async def allow_writer(*_args):
        return None

    async def find_project(*_args):
        return object()

    monkeypatch.setattr(prompt_router, "require_project_writer", allow_writer)
    monkeypatch.setattr(ProjectRepository, "get_by_id", find_project)

    prompt = SimpleNamespace(project_id=10, is_active=True, models=[object()])
    prompt_service = SimpleNamespace(
        prompt_repo=SimpleNamespace(session=object()),
        get_prompt=lambda _prompt_id: None,
    )

    async def get_prompt(_prompt_id):
        return prompt

    prompt_service.get_prompt = get_prompt

    class RunService:
        async def run_prompt_model(self, received_prompt, model_id):
            return [(received_prompt, model_id)]

        async def run_prompt_models(self, _prompt):
            raise AssertionError("all-model path should not run")

    result = await prompt_router.run_prompt(
        project_id=10,
        prompt_id=31,
        ai_model_id=94,
        prompt_service=prompt_service,
        run_service=RunService(),
        current_user=SimpleNamespace(id=7),
    )

    assert result == [(prompt, 94)]
