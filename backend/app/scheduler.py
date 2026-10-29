import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.database.connection import async_session_maker
from app.database.models import Prompt, PromptModel
from app.infrastructure.redis_client import get_redis
from app.infrastructure.run_queue import PromptRunJob, PromptRunQueue
from app.repositories.prompt_repository import PromptRepository
from app.repositories.daily_model_run_repository import DailyModelRunRepository

logger = logging.getLogger(__name__)


async def _enqueue_daily_jobs(queue: PromptRunQueue, run_date) -> int:
    """09:00 Tehran: enqueue all active prompts with all active model names."""
    count = 0
    async with async_session_maker() as session:
        await PromptRepository(session).purge_archived_before(datetime.now(timezone.utc) - timedelta(days=30))
        prompts = (await session.execute(
            select(Prompt)
            .options(selectinload(Prompt.models).selectinload(PromptModel.model))
            .where(Prompt.is_active.is_(True))
        )).scalars().all()
        for prompt in prompts:
            model_names = tuple(
                link.model.model_key
                for link in prompt.models
                if link.model.is_active
            )
            if not model_names:
                continue
            if await queue.enqueue_once(PromptRunJob(
                prompt.id, 0, run_date.isoformat(), source="scheduled", models=model_names,
            )):
                count += 1
    return count


async def _enqueue_retry_jobs(queue: PromptRunQueue, run_date) -> int:
    """Every DAILY_RETRY_POLL_MINUTES: enqueue prompts with retrying models due now."""
    count = 0
    now = datetime.now(timezone.utc)
    async with async_session_maker() as session:
        dmr_repo = DailyModelRunRepository(session)
        retrying = await dmr_repo.get_retrying_models(run_date, now=now)
        by_prompt: dict[int, list[str]] = {}
        for prompt_id, model in retrying:
            by_prompt.setdefault(prompt_id, []).append(model)
        for prompt_id, models in by_prompt.items():
            if await queue.enqueue_once(PromptRunJob(
                prompt_id, 0, run_date.isoformat(), source="retry", models=tuple(models),
            )):
                count += 1
    return count


async def _retry_extractions() -> int:
    """Retry a small, bounded batch of failed brand extractions older than 1 hour.

    Limits (batch size, max attempts, backoff) live in AIRunService.retry_failed_extractions
    and come from settings, so this cannot hammer the extraction model every minute.
    """
    from app.services.ai_run_service import AIRunService
    from app.repositories.ai_run_repository import AIRunRepository
    from app.services.brand_extraction_service import BrandExtractionService
    from app.services.brand_persistence_service import BrandPersistenceService
    from app.services.ai_service import AIService

    count = 0
    async with async_session_maker() as session:
        ai_service = AIService()
        service = AIRunService(
            AIRunRepository(session), ai_service,
            BrandExtractionService(ai_service, session),
            BrandPersistenceService(session),
        )
        try:
            results = await service.retry_failed_extractions(older_than_hours=1)
            count = len(results)
            if count:
                logger.info("extraction_retries_done", extra={"event_data": {"count": count}})
        except Exception:
            logger.exception("extraction_retry_cycle_failed")
        finally:
            await AIService.close()
    return count


async def schedule_once() -> int:
    redis = get_redis()
    queue = PromptRunQueue(redis)
    lock_token = await queue.acquire_scheduler_lock()
    if not lock_token:
        return 0
    try:
        local_now = datetime.now(ZoneInfo(settings.RUN_TIMEZONE))
        run_date = local_now.date()
        count = 0

        if local_now.hour == 9:
            count += await _enqueue_daily_jobs(queue, run_date)

        count += await _enqueue_retry_jobs(queue, run_date)
        count += await _retry_extractions()

        if count:
            logger.info("prompt_jobs_scheduled", extra={"event_data": {"job_count": count}})
        return count
    finally:
        await queue.release_scheduler_lock(lock_token)


async def main() -> None:
    while True:
        try:
            await schedule_once()
        except Exception:
            logger.exception("prompt_scheduler_cycle_failed")
        await asyncio.sleep(settings.AUTOMATIC_RUN_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
