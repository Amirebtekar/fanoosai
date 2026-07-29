import asyncio
import logging
from dataclasses import replace
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from sqlalchemy.orm import selectinload

from app.database.connection import async_session_maker
from app.database.models import Prompt, PromptModel
from app.infrastructure.redis_client import get_redis
from app.infrastructure.run_queue import PromptRunJob, PromptRunQueue
from app.observability import QUEUE_JOBS
from app.repositories.ai_run_repository import AIRunRepository
from app.services.ai_run_service import AIRunService
from app.services.ai_service import AIService
from app.services.brand_extraction_service import BrandExtractionService
from app.services.brand_persistence_service import BrandPersistenceService
from app.core.config import settings
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def process_job(queue: PromptRunQueue, entry_id: str, job) -> None:
    async with async_session_maker() as session:
        ai_service = AIService()
        service = AIRunService(
            AIRunRepository(session), ai_service, BrandExtractionService(ai_service),
            BrandPersistenceService(session), queue,
        )
        if job.source == "extraction_retry":
            if job.ai_run_id is not None:
                await service.retry_extraction(job.ai_run_id, job.run_attempt)
            await queue.ack(entry_id)
            return
        prompt = (await session.execute(
            select(Prompt)
            .options(selectinload(Prompt.models).selectinload(PromptModel.model))
            .where(Prompt.id == job.prompt_id, Prompt.is_active.is_(True))
        )).scalar_one_or_none()
        if prompt is None:
            await queue.ack(entry_id)
            return
        run_at = datetime.combine(
            date.fromisoformat(job.run_date), time.min, tzinfo=ZoneInfo(settings.RUN_TIMEZONE)
        )
        await service.run_prompt_model(prompt, job.ai_model_id, now=run_at, source=job.source, run_attempt=job.run_attempt)
        await queue.ack(entry_id)


async def main() -> None:
    queue = PromptRunQueue(get_redis())
    await queue.ensure_group()
    try:
        while True:
            await queue.enqueue_due_retries()
            for entry_id, job in await queue.read():
                try:
                    await process_job(queue, entry_id, job)
                    QUEUE_JOBS.labels("success").inc()
                except Exception:
                    if job.attempts < settings.REDIS_JOB_MAX_RETRIES:
                        retry_job = replace(job, attempts=job.attempts + 1)
                        if job.source == "scheduled":
                            await queue.enqueue_after_claim_lease(retry_job)
                        else:
                            await queue.enqueue_retry(retry_job)
                        QUEUE_JOBS.labels("retry").inc()
                    else:
                        QUEUE_JOBS.labels("failed").inc()
                    await queue.ack(entry_id)
                    logger.exception("prompt_job_failed", extra={"event_data": {"entry_id": entry_id}})
    finally:
        await AIService.close()


if __name__ == "__main__":
    asyncio.run(main())
