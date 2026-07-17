from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from app.database.models import AIRun, DailyPromptRun, Prompt


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
        await self.session.execute(
            update(Prompt).where(Prompt.id == prompt_id).values(last_run_at=now)
        )
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def update_extraction(self, run: AIRun, status: str, error: str | None = None) -> None:
        run.extraction_status = status
        run.error_message = error
        run.processed_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def claim_daily_run(self, prompt_id: int, ai_model_id: int, run_date: date) -> bool:
        """Atomically claim one prompt/model execution for a calendar day."""
        existing = await self.session.scalar(
            select(DailyPromptRun.id).where(
                DailyPromptRun.prompt_id == prompt_id,
                DailyPromptRun.ai_model_id == ai_model_id,
                DailyPromptRun.run_date == run_date,
            )
        )
        if existing is not None:
            return False

        self.session.add(DailyPromptRun(
            prompt_id=prompt_id,
            ai_model_id=ai_model_id,
            run_date=run_date,
            claimed_at=datetime.now(timezone.utc),
        ))
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            return False
        return True

    async def get_by_prompt(self, prompt_id: int) -> list[AIRun]:
        stmt = (
            select(AIRun)
            .options(selectinload(AIRun.model))
            .where(AIRun.prompt_id == prompt_id)
            .order_by(AIRun.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
