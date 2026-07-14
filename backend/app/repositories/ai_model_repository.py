from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AIModel

class AIModelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(self) -> list[AIModel]:
        stmt = select(AIModel).where(AIModel.is_active == True).order_by(AIModel.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, model_id: int) -> AIModel | None:
        stmt = select(AIModel).where(AIModel.id == model_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, name: str, provider: str, model_key: str, is_active: bool = True) -> AIModel:
        model = AIModel(name=name, provider=provider, model_key=model_key, is_active=is_active)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def sync_from_gateway(self, rows: list[dict]) -> list[AIModel]:
        keys = {row["model_key"] for row in rows}
        result = await self.session.execute(select(AIModel))
        existing = {model.model_key: model for model in result.scalars().all()}

        synced = []
        now = datetime.now(timezone.utc)
        for row in rows:
            model = existing.get(row["model_key"])
            if model:
                model.name = row["name"]
                model.provider = row["provider"]
                model.is_active = True
                model.updated_at = now
            else:
                model = AIModel(**row, is_active=True, updated_at=now)
                self.session.add(model)
            synced.append(model)

        for model_key, model in existing.items():
            if model_key not in keys:
                model.is_active = False

        await self.session.commit()
        for model in synced:
            await self.session.refresh(model)
        return synced
