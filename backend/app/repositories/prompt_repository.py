from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List

from app.database.models import AIModel, Prompt, PromptModel

class PromptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_id: int, text: str, model_ids: list[int] | None = None) -> Prompt:
        prompt = Prompt(project_id=project_id, text=text)
        self.session.add(prompt)
        await self.session.flush()
        for model_id in model_ids or []:
            self.session.add(PromptModel(prompt_id=prompt.id, ai_model_id=model_id))
        await self.session.commit()
        return await self.get_by_id(prompt.id)

    async def get_by_id(self, prompt_id: int) -> Prompt | None:
        stmt = (
            select(Prompt)
            .options(selectinload(Prompt.models).selectinload(PromptModel.model))
            .where(Prompt.id == prompt_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def active_model_ids(self, model_ids: list[int]) -> set[int]:
        stmt = select(AIModel.id).where(AIModel.id.in_(model_ids), AIModel.is_active == True)
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def add_model(self, prompt_id: int, model_id: int) -> bool:
        existing = await self.session.execute(
            select(PromptModel.id).where(
                PromptModel.prompt_id == prompt_id,
                PromptModel.ai_model_id == model_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return False
        self.session.add(PromptModel(prompt_id=prompt_id, ai_model_id=model_id))
        await self.session.commit()
        return True

    async def remove_model(self, prompt_id: int, model_id: int) -> bool:
        result = await self.session.execute(
            delete(PromptModel).where(
                PromptModel.prompt_id == prompt_id,
                PromptModel.ai_model_id == model_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def exists_by_text(self, project_id: int, text: str) -> bool:
        """Check if an active prompt with the same text exists in the project."""
        stmt = select(Prompt.id).where(
            Prompt.project_id == project_id,
            Prompt.text == text,
            Prompt.is_active == True
        ).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_by_project(self, project_id: int, include_archived: bool = False) -> List[Prompt]:
        stmt = (
            select(Prompt)
            .options(selectinload(Prompt.models).selectinload(PromptModel.model))
            .where(Prompt.project_id == project_id)
        )
        if not include_archived:
            stmt = stmt.where(Prompt.is_active == True)
        stmt = stmt.order_by(Prompt.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active_by_project(self, project_id: int) -> int:
        stmt = select(func.count(Prompt.id)).where(
            Prompt.project_id == project_id, 
            Prompt.is_active == True
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def archive(self, prompt: Prompt) -> Prompt:
        prompt.is_active = False
        await self.session.commit()
        await self.session.refresh(prompt)
        return prompt