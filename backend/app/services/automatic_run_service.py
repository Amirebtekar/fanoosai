import asyncio
import logging

from app.core.config import settings
from app.database.connection import async_session_maker
from app.database.models import Prompt, PromptModel
from app.repositories.ai_run_repository import AIRunRepository
from app.services.ai_run_service import AIRunService
from app.services.ai_service import AIService
from app.services.brand_extraction_service import BrandExtractionService
from app.services.brand_persistence_service import BrandPersistenceService
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


async def run_active_prompts_once() -> None:
    async with async_session_maker() as session:
        prompts = list((await session.execute(
            select(Prompt)
            .options(selectinload(Prompt.models).selectinload(PromptModel.model))
            .where(Prompt.is_active.is_(True))
        )).scalars().all())

        ai_service = AIService()
        run_service = AIRunService(
            AIRunRepository(session),
            ai_service,
            BrandExtractionService(ai_service),
            BrandPersistenceService(session),
        )
        for prompt in prompts:
            try:
                await run_service.run_prompt_models(prompt)
            except Exception:
                logger.exception("Automatic run failed for prompt %s", prompt.id)


async def automatic_run_loop() -> None:
    """Poll active prompts; the database claim makes each model run once per day."""
    while True:
        try:
            await run_active_prompts_once()
        except Exception:
            logger.exception("Automatic prompt run cycle failed")
        await asyncio.sleep(settings.AUTOMATIC_RUN_INTERVAL_SECONDS)
