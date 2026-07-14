from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import AIRun


class AIRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        prompt_id: int,
        ai_model_id: int,
        request_text: str,
        response_text: str | None = None,
        status: str = "failed",
        error_message: str | None = None,
    ) -> AIRun:
        now = datetime.now(timezone.utc)
        run = AIRun(
            prompt_id=prompt_id,
            ai_model_id=ai_model_id,
            request_text=request_text,
            response_text=response_text,
            status=status,
            extraction_status="pending" if status == "success" else "failed",
            error_message=error_message,
            completed_at=now if status != "running" else None,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def update_extraction(self, run: AIRun, status: str, error: str | None = None) -> None:
        run.extraction_status = status
        run.error_message = error
        run.processed_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def get_by_prompt(self, prompt_id: int) -> list[AIRun]:
        stmt = (
            select(AIRun)
            .options(selectinload(AIRun.model))
            .where(AIRun.prompt_id == prompt_id)
            .order_by(AIRun.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
