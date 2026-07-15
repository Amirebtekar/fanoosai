from typing import List

from app.database.models import Prompt, Project
from app.repositories.prompt_repository import PromptRepository
from app.repositories.project_repository import ProjectRepository

class PromptService:
    MAX_ACTIVE_PROMPTS = 10
    MIN_ACTIVE_PROMPTS = 1

    def __init__(self, prompt_repo: PromptRepository, project_repo: ProjectRepository):
        self.prompt_repo = prompt_repo
        self.project_repo = project_repo

    async def create_prompt(self, project_id: int, text: str, model_ids: list[int] | None = None) -> Prompt:
        # Verify project exists
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise ValueError("پروژه یافت نشد")

        # Check duplicate active prompt
        if await self.prompt_repo.exists_by_text(project_id, text):
            raise ValueError("یک Prompt با همین متن قبلاً اضافه شده است")

        # Check active prompts limit
        active_count = await self.prompt_repo.count_active_by_project(project_id)
        if active_count >= self.MAX_ACTIVE_PROMPTS:
            raise ValueError(f"حداکثر {self.MAX_ACTIVE_PROMPTS} Prompt فعال مجاز است")

        model_ids = list(dict.fromkeys(model_ids or []))
        if model_ids:
            active_ids = await self.prompt_repo.active_model_ids(model_ids)
            if active_ids != set(model_ids):
                raise ValueError("یک یا چند مدل AI معتبر یا فعال نیست")

        return await self.prompt_repo.create(project_id, text, model_ids)

    async def get_prompt(self, prompt_id: int) -> Prompt:
        prompt = await self.prompt_repo.get_by_id(prompt_id)
        if not prompt:
            raise ValueError("Prompt یافت نشد")
        return prompt

    async def list_project_prompts(self, project_id: int, include_archived: bool = False) -> List[Prompt]:
        return await self.prompt_repo.list_by_project(project_id, include_archived)

    async def add_prompt_model(self, prompt_id: int, model_id: int) -> None:
        await self.get_prompt(prompt_id)
        if await self.prompt_repo.active_model_ids([model_id]) != {model_id}:
            raise ValueError("مدل AI معتبر یا فعال نیست")
        if not await self.prompt_repo.add_model(prompt_id, model_id):
            raise ValueError("این مدل قبلاً برای Prompt انتخاب شده است")

    async def remove_prompt_model(self, prompt_id: int, model_id: int) -> None:
        await self.get_prompt(prompt_id)
        if not await self.prompt_repo.remove_model(prompt_id, model_id):
            raise ValueError("این مدل برای Prompt انتخاب نشده است")

    async def archive_prompt(self, prompt_id: int) -> Prompt:
        prompt = await self.get_prompt(prompt_id)

        # Check minimum active prompts
        active_count = await self.prompt_repo.count_active_by_project(prompt.project_id)
        if active_count <= self.MIN_ACTIVE_PROMPTS:
            raise ValueError(f"حداقل {self.MIN_ACTIVE_PROMPTS} Prompt فعال باید وجود داشته باشد")

        return await self.prompt_repo.archive(prompt)