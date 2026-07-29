from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from app.database.models import AIRun, DailyPromptRun, Prompt, Alert, AlertRule, ProjectBrand, RunBrand
from app.core.config import settings


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
        provider_used: str | None = None,
    ) -> AIRun:
        now = datetime.now(timezone.utc)
        run = AIRun(
            prompt_id=prompt_id,
            ai_model_id=ai_model_id,
            request_text=request_text,
            response_text=response_text,
            status=status,
            provider_used=provider_used,
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

    async def claim_daily_run(
        self, prompt_id: int, ai_model_id: int, run_date: date, source: str
    ) -> bool:
        """Claim a daily execution, recovering claims abandoned before a run was saved."""
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=settings.RUN_CLAIM_LEASE_SECONDS)
        reclaimed = await self.session.execute(
            update(DailyPromptRun)
            .where(
                DailyPromptRun.prompt_id == prompt_id,
                DailyPromptRun.ai_model_id == ai_model_id,
                DailyPromptRun.run_date == run_date,
                DailyPromptRun.status == "claimed",
                DailyPromptRun.claimed_at < stale_before,
            )
            .values(source=source, claimed_at=now)
        )
        if reclaimed.rowcount:
            await self.session.commit()
            return True

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
            source=source,
            status="claimed",
            claimed_at=now,
        ))
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            return False
        return True

    async def complete_daily_run(
        self, prompt_id: int, ai_model_id: int, run_date: date
    ) -> None:
        await self.session.execute(
            update(DailyPromptRun)
            .where(
                DailyPromptRun.prompt_id == prompt_id,
                DailyPromptRun.ai_model_id == ai_model_id,
                DailyPromptRun.run_date == run_date,
            )
            .values(status="completed")
        )
        await self.session.commit()

    async def get_daily_claim_sources(
        self, prompt_id: int, ai_model_ids: list[int], run_date: date
    ) -> dict[int, str]:
        if not ai_model_ids:
            return {}
        rows = await self.session.execute(
            select(DailyPromptRun.ai_model_id, DailyPromptRun.source).where(
                DailyPromptRun.prompt_id == prompt_id,
                DailyPromptRun.ai_model_id.in_(ai_model_ids),
                DailyPromptRun.run_date == run_date,
            )
        )
        return dict(rows.all())

    async def get_by_prompt(self, prompt_id: int) -> list[AIRun]:
        stmt = (
            select(AIRun)
            .options(selectinload(AIRun.model))
            .where(AIRun.prompt_id == prompt_id)
            .order_by(AIRun.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, run_id: int) -> AIRun | None:
        return await self.session.get(AIRun, run_id)

    async def alert_run_failure(self, prompt_id: int, message: str) -> None:
        project_id = await self.session.scalar(select(Prompt.project_id).where(Prompt.id == prompt_id))
        if project_id is None:
            return
        rule = await self.session.scalar(select(AlertRule).where(AlertRule.project_id == project_id, AlertRule.kind == "run_failure"))
        if rule is None:
            return
        now = datetime.now(timezone.utc)
        if rule.last_triggered_at and (now - rule.last_triggered_at).total_seconds() < rule.cooldown_hours * 3600:
            return
        self.session.add(Alert(project_id=project_id, kind="run_failure", message=message))
        rule.last_triggered_at = now
        await self.session.commit()

    async def alert_new_competitor(self, prompt_id: int, names: list[str]) -> None:
        project_id = await self.session.scalar(select(Prompt.project_id).where(Prompt.id == prompt_id))
        if project_id is None:
            return
        known = set((await self.session.scalars(select(ProjectBrand.name).where(ProjectBrand.project_id == project_id))).all())
        new = next((name for name in names if name not in known), None)
        rule = await self.session.scalar(select(AlertRule).where(AlertRule.project_id == project_id, AlertRule.kind == "new_competitor"))
        if not new or rule is None:
            return
        now = datetime.now(timezone.utc)
        if rule.last_triggered_at and (now - rule.last_triggered_at).total_seconds() < rule.cooldown_hours * 3600:
            return
        self.session.add(Alert(project_id=project_id, kind="new_competitor", message=f"New competitor detected: {new}"))
        rule.last_triggered_at = now
        await self.session.commit()

    async def alert_rank_changes(self, run_id: int) -> None:
        run = await self.session.get(AIRun, run_id)
        if run is None:
            return
        project_id = await self.session.scalar(select(Prompt.project_id).where(Prompt.id == run.prompt_id))
        previous = await self.session.scalar(select(func.max(AIRun.id)).where(AIRun.prompt_id == run.prompt_id, AIRun.ai_model_id == run.ai_model_id, AIRun.id < run_id, AIRun.status == "success"))
        if not previous:
            return
        current = {brand_id: rank for brand_id, rank in (await self.session.execute(select(RunBrand.brand_id, RunBrand.rank).where(RunBrand.ai_run_id == run_id))).all()}
        prior = {brand_id: rank for brand_id, rank in (await self.session.execute(select(RunBrand.brand_id, RunBrand.rank).where(RunBrand.ai_run_id == previous))).all()}
        rules = {rule.kind: rule for rule in (await self.session.scalars(select(AlertRule).where(AlertRule.project_id == project_id, AlertRule.kind.in_(("rank_drop", "disappearance"))))).all()}
        now = datetime.now(timezone.utc)
        for kind, message in (("rank_drop", next((f"Rank dropped from {prior[key]} to {current[key]}" for key in current if key in prior and current[key] > prior[key]), None)), ("disappearance", "A previously visible brand disappeared" if set(prior) - set(current) else None)):
            rule = rules.get(kind)
            if message and rule and (not rule.last_triggered_at or (now - rule.last_triggered_at).total_seconds() >= rule.cooldown_hours * 3600):
                self.session.add(Alert(project_id=project_id, kind=kind, message=message)); rule.last_triggered_at = now
        await self.session.commit()
