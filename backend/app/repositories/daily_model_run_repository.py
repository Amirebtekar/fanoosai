from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.models import DailyModelRun


class DailyModelRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_rows(self, prompt_id: int, models: list[str], run_date: date) -> list[DailyModelRun]:
        """Ensure a row exists for each model of the prompt for run_date. Returns all rows."""
        existing = await self.session.execute(
            select(DailyModelRun).where(
                DailyModelRun.prompt_id == prompt_id,
                DailyModelRun.run_date == run_date,
            )
        )
        rows = {r.model: r for r in existing.scalars().all()}
        for model in models:
            if model not in rows:
                row = DailyModelRun(
                    prompt_id=prompt_id, model=model, run_date=run_date,
                    status="pending", attempts=0, max_attempts=settings.DAILY_MAX_ATTEMPTS,
                )
                self.session.add(row)
                rows[model] = row
        await self.session.commit()
        for r in rows.values():
            await self.session.refresh(r)
        return list(rows.values())

    async def get_rows(self, prompt_id: int, run_date: date) -> list[DailyModelRun]:
        result = await self.session.execute(
            select(DailyModelRun).where(
                DailyModelRun.prompt_id == prompt_id,
                DailyModelRun.run_date == run_date,
            )
        )
        return list(result.scalars().all())

    async def get_row(self, prompt_id: int, model: str, run_date: date) -> DailyModelRun | None:
        result = await self.session.execute(
            select(DailyModelRun).where(
                DailyModelRun.prompt_id == prompt_id,
                DailyModelRun.model == model,
                DailyModelRun.run_date == run_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_runnable(self, prompt_id: int, run_date: date, now: datetime | None = None) -> list[DailyModelRun]:
        """Return rows in 'pending' or 'retrying' with next_attempt_at <= now."""
        if now is None:
            now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(DailyModelRun).where(
                DailyModelRun.prompt_id == prompt_id,
                DailyModelRun.run_date == run_date,
                DailyModelRun.status.in_(["pending", "retrying"]),
            )
        )
        rows = list(result.scalars().all())
        runnable = []
        for r in rows:
            if r.status == "pending":
                runnable.append(r)
            elif r.status == "retrying" and (r.next_attempt_at is None or r.next_attempt_at <= now):
                runnable.append(r)
        return runnable

    async def acquire_lock(self, prompt_id: int, model: str, run_date: date, lease_seconds: int = 600) -> bool:
        """Try to acquire a lock on (prompt_id, model, run_date). Returns True if acquired."""
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(seconds=lease_seconds)
        result = await self.session.execute(
            update(DailyModelRun)
            .where(
                DailyModelRun.prompt_id == prompt_id,
                DailyModelRun.model == model,
                DailyModelRun.run_date == run_date,
                DailyModelRun.status.in_(["pending", "retrying"]),
                (DailyModelRun.locked_at.is_(None)) | (DailyModelRun.locked_at < stale_before),
            )
            .values(locked_at=now)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def release_lock(self, prompt_id: int, model: str, run_date: date) -> None:
        await self.session.execute(
            update(DailyModelRun)
            .where(
                DailyModelRun.prompt_id == prompt_id,
                DailyModelRun.model == model,
                DailyModelRun.run_date == run_date,
            )
            .values(locked_at=None)
        )
        await self.session.commit()

    async def mark_success(self, prompt_id: int, model: str, run_date: date, run_id: int) -> None:
        row = await self.get_row(prompt_id, model, run_date)
        new_attempts = (row.attempts + 1) if row else 1
        await self.session.execute(
            update(DailyModelRun)
            .where(
                DailyModelRun.prompt_id == prompt_id,
                DailyModelRun.model == model,
                DailyModelRun.run_date == run_date,
            )
            .values(
                status="success", success_run_id=run_id, attempts=new_attempts,
                last_error_message=None, last_error_provider=None,
                last_error_status=None, last_error_retryable=None,
                next_attempt_at=None, locked_at=None,
            )
        )
        await self.session.commit()

    async def mark_failure(
        self, prompt_id: int, model: str, run_date: date,
        error_message: str | None = None,
        error_provider: str | None = None,
        error_status: int | None = None,
        error_retryable: bool | None = None,
        retry_interval_minutes: int = 15,
    ) -> str:
        """Record a failed attempt. Returns the new status ('retrying' or 'exhausted')."""
        row = await self.get_row(prompt_id, model, run_date)
        if row is None:
            return "exhausted"
        new_attempts = row.attempts + 1
        is_retryable = error_retryable is not False
        if is_retryable and new_attempts < row.max_attempts:
            new_status = "retrying"
            next_at = datetime.now(timezone.utc) + timedelta(minutes=retry_interval_minutes)
        else:
            new_status = "exhausted"
            next_at = None
        await self.session.execute(
            update(DailyModelRun)
            .where(
                DailyModelRun.prompt_id == prompt_id,
                DailyModelRun.model == model,
                DailyModelRun.run_date == run_date,
            )
            .values(
                status=new_status, attempts=new_attempts,
                last_error_message=error_message,
                last_error_provider=error_provider,
                last_error_status=error_status,
                last_error_retryable=error_retryable,
                next_attempt_at=next_at, locked_at=None,
            )
        )
        await self.session.commit()
        return new_status

    async def reset_for_manual(self, prompt_id: int, models: list[str], run_date: date, mode: str = "failed") -> list[DailyModelRun]:
        """Reset rows for manual rerun. mode='failed' resets retrying/exhausted; mode='all' resets all."""
        rows = [row for row in await self.get_rows(prompt_id, run_date) if row.model in models]
        result = []
        for row in rows:
            if mode == "all":
                row.status = "pending"
                row.attempts = 0
                row.next_attempt_at = None
                row.success_run_id = None
                row.locked_at = None
                result.append(row)
            elif row.status in ("retrying", "exhausted"):
                row.status = "pending"
                row.attempts = 0
                row.next_attempt_at = None
                row.locked_at = None
                result.append(row)
        await self.session.commit()
        return result

    async def get_retrying_models(self, run_date: date, now: datetime | None = None) -> list[tuple[int, str]]:
        """Return (prompt_id, model) pairs with status='retrying' and next_attempt_at <= now."""
        if now is None:
            now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(DailyModelRun.prompt_id, DailyModelRun.model).where(
                DailyModelRun.run_date == run_date,
                DailyModelRun.status == "retrying",
                DailyModelRun.next_attempt_at.isnot(None),
                DailyModelRun.next_attempt_at <= now,
            )
        )
        return list(result.all())

    async def remove_model(self, prompt_id: int, model: str, run_date: date) -> None:
        await self.session.execute(
            delete(DailyModelRun).where(
                DailyModelRun.prompt_id == prompt_id,
                DailyModelRun.model == model,
                DailyModelRun.run_date == run_date,
            )
        )
        await self.session.commit()
