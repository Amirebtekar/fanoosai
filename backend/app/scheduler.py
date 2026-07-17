import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.database.connection import async_session_maker
from app.database.models import Prompt, PromptModel
from app.infrastructure.redis_client import get_redis
from app.infrastructure.run_queue import PromptRunJob, PromptRunQueue

logger = logging.getLogger(__name__)


async def schedule_once() -> int:
    redis = get_redis()
    queue = PromptRunQueue(redis)
    lock_token = await queue.acquire_scheduler_lock()
    if not lock_token:
        return 0
    count = 0
    try:
        run_date = datetime.now(ZoneInfo(settings.RUN_TIMEZONE)).date()
        async with async_session_maker() as session:
            prompts = (await session.execute(
                select(Prompt)
                .options(selectinload(Prompt.models).selectinload(PromptModel.model))
                .where(Prompt.is_active.is_(True))
            )).scalars().all()
            for prompt in prompts:
                for link in prompt.models:
                    if not link.model.is_active:
                        continue
                    if await queue.enqueue_once(PromptRunJob(prompt.id, link.ai_model_id, run_date.isoformat())):
                        count += 1
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
