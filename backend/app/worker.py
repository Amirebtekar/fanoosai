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
from app.repositories.daily_model_run_repository import DailyModelRunRepository
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.services.daily_model_run_service import DailyModelRunService
from app.services.ai_service import AIService
from app.services.brand_extraction_service import BrandExtractionService
from app.services.brand_persistence_service import BrandPersistenceService
from app.core.config import settings
from sqlalchemy import select

logger = logging.getLogger(__name__)
_request_lock = asyncio.Lock()
_last_request_at = 0.0


async def process_job(queue: PromptRunQueue, entry_id: str, job) -> None:
    global _last_request_at
    async with async_session_maker() as session:
        ai_service = AIService()
        dmr_repo = DailyModelRunRepository(session)
        run_repo = AIRunRepository(session)
        service = DailyModelRunService(
            dmr_repo, run_repo, ai_service,
            BrandExtractionService(ai_service, session),
            BrandPersistenceService(session),
        )

        prompt = (await session.execute(
            select(Prompt)
            .options(selectinload(Prompt.models).selectinload(PromptModel.model))
            .where(Prompt.id == job.prompt_id, Prompt.is_active.is_(True))
        )).scalar_one_or_none()
        if prompt is None:
            await queue.ack(entry_id)
            return

        run_date = date.fromisoformat(job.run_date)

        async with _request_lock:
            wait = settings.WORKER_REQUEST_DELAY_SECONDS - (asyncio.get_running_loop().time() - _last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_request_at = asyncio.get_running_loop().time()

        if job.models:
            target_models = list(job.models)
        else:
            target_models = [link.model.model_key for link in prompt.models if link.model.is_active]

        await service.run_daily(prompt, run_date=run_date, model_filter=target_models)

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
                    QUEUE_JOBS.labels("failed").inc()
                    await queue.ack(entry_id)
                    logger.exception("prompt_job_failed", extra={"event_data": {"entry_id": entry_id}})
    finally:
        await AIService.close()


if __name__ == "__main__":
    asyncio.run(main())
