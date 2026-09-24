from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AIModel, AIRun, PromptModel

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

    async def save_gateway_selection(self, rows: list[dict], active_model_keys: set[str]) -> list[AIModel]:
        result = await self.session.execute(select(AIModel))
        existing = {model.model_key: model for model in result.scalars().all()}
        now = datetime.now(timezone.utc)
        for row in rows:
            model = existing.get(row["model_key"])
            if model is None:
                model = AIModel(**row, is_active=False, updated_at=now)
                self.session.add(model)
            else:
                model.name = row["name"]
                model.provider = row["provider"]
                model.updated_at = now
            model.is_active = row["model_key"] in active_model_keys
        gateway_keys = {row["model_key"] for row in rows}
        for model in existing.values():
            if model.model_key not in gateway_keys:
                model.is_active = False
        await self.session.flush()
        all_models = list((await self.session.execute(select(AIModel))).scalars().all())
        await self._merge_equivalent_models(all_models, active_model_keys)
        await self.session.commit()
        result = await self.session.execute(select(AIModel).order_by(AIModel.name))
        return list(result.scalars().all())

    async def _merge_equivalent_models(self, models: list[AIModel], active_model_keys: set[str]) -> None:
        groups: dict[str, list[AIModel]] = {}
        for model in models:
            groups.setdefault(model.model_key.rsplit('/', 1)[-1], []).append(model)
        links = list((await self.session.execute(select(PromptModel))).scalars().all())
        runs = list((await self.session.execute(select(AIRun))).scalars().all())
        for group in groups.values():
            if len(group) < 2:
                continue
            canonical = next((model for model in group if model.model_key in active_model_keys), None) or next((model for model in group if model.is_active), None) or group[0]
            for duplicate in group:
                if duplicate.id == canonical.id:
                    continue
                for link in links:
                    if link.ai_model_id != duplicate.id:
                        continue
                    if any(item.prompt_id == link.prompt_id and item.ai_model_id == canonical.id for item in links):
                        await self.session.delete(link)
                    else:
                        link.ai_model_id = canonical.id
                for run in runs:
                    if run.ai_model_id == duplicate.id:
                        run.ai_model_id = canonical.id
                await self.session.delete(duplicate)

    async def sync_from_gateway(self, rows: list[dict]) -> list[AIModel]:
        result = await self.session.execute(select(AIModel))
        existing = {model.model_key: model for model in result.scalars().all()}

        synced = []
        now = datetime.now(timezone.utc)
        for row in rows:
            aliases = {row["model_key"], f"openai/{row['model_key']}"}
            matches = [model for key, model in existing.items() if key in aliases or key.rsplit('/', 1)[-1] == row["model_key"]]
            if matches:
                for model in matches:
                    model.name = row["name"]
                    model.provider = row["provider"]
                    model.is_active = True
                    model.updated_at = now
                synced.extend(matches)
            else:
                model = AIModel(**row, is_active=True, updated_at=now)
                self.session.add(model)
                synced.append(model)

        available_keys = {row["model_key"] for row in rows}
        for model_key, model in existing.items():
            if model_key not in available_keys and model_key.rsplit('/', 1)[-1] not in available_keys:
                model.is_active = False

        await self.session.commit()
        for model in synced:
            await self.session.refresh(model)
        return synced
