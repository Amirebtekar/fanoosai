import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.database.models import Prompt
from app.infrastructure.run_queue import PromptRunQueue
from app.repositories.ai_run_repository import AIRunRepository
from app.repositories.system_settings_repository import (
    DOMAIN_INSTRUCTION_KEY,
    SystemSettingsRepository,
    get_setting,
)
from app.services.ai_service import AIService
from app.services.brand_extraction_service import BrandExtractionService
from app.services.brand_persistence_service import BrandPersistenceService

DOMAIN_FORMAT_INSTRUCTION = (
    "اگر نام برندی می‌آوری، دامنه رسمی آن را کنار نام به شکل «برند (example.com)» بنویس. "
    "دامنه را حدس نزن؛ اگر مطمئن نیستی، آن را نیاور. به این دستور در پاسخ اشاره نکن."
)
logger = logging.getLogger(__name__)

class AIRunService:
    def __init__(
        self,
        run_repo: AIRunRepository,
        ai_service: AIService,
        extraction_service: BrandExtractionService,
        persistence_service: BrandPersistenceService,
        retry_queue: PromptRunQueue | None = None,
        system_settings: SystemSettingsRepository | None = None,
    ):
        self.run_repo = run_repo
        self.ai_service = ai_service
        self.extraction_service = extraction_service
        self.persistence_service = persistence_service
        self.retry_queue = retry_queue
        self.system_settings = system_settings

    @staticmethod
    def _run_date(now: datetime | None) -> date:
        timezone = ZoneInfo(settings.RUN_TIMEZONE)
        if now is None:
            return datetime.now(timezone).date()
        return (now.astimezone(timezone) if now.tzinfo else now).date()

    async def run_prompt_models(
        self, prompt: Prompt, *, now: datetime | None = None, source: str = "manual", run_attempt: int = 1
    ) -> list[dict]:
        results = []
        for link in prompt.models:
            results.extend(await self.run_prompt_model(prompt, link.model.id, now=now, source=source, run_attempt=run_attempt))
        return results

    async def execution_availability(
        self, prompt: Prompt, *, now: datetime | None = None
    ) -> list[dict]:
        run_date = self._run_date(now)
        model_ids = [link.model.id for link in prompt.models]
        claims = await self.run_repo.get_daily_claim_sources(prompt.id, model_ids, run_date)
        return [
            {
                "model_id": link.model.id,
                "model_name": link.model.name,
                "model_is_active": bool(getattr(link.model, "is_active", True)),
                "can_run": bool(getattr(link.model, "is_active", True)) and link.model.id not in claims,
                "claim_source": claims.get(link.model.id),
            }
            for link in prompt.models
        ]

    async def run_prompt_model(
        self, prompt: Prompt, ai_model_id: int, *, now: datetime | None = None, source: str = "manual", run_attempt: int = 1
    ) -> list[dict]:
        link = next((item for item in prompt.models if getattr(item, "ai_model_id", item.model.id) == ai_model_id), None)
        if link is None:
            return []
        model = link.model
        run_date = self._run_date(now)
        if source not in {"manual", "scheduled", "retry"}:
            raise ValueError("Invalid run source")
        if not getattr(model, "is_active", True):
            return []
        if source != "retry" and not await self.run_repo.claim_daily_run(prompt.id, model.id, run_date, source):
            return []
        domain_instruction = DOMAIN_FORMAT_INSTRUCTION
        if self.system_settings is not None:
            domain_instruction = await get_setting(self.system_settings.session, DOMAIN_INSTRUCTION_KEY, DOMAIN_FORMAT_INSTRUCTION)
        request_text = f"{prompt.text}\n\n{domain_instruction}"
        try:
            response_text, provider_used = await self.ai_service.run_prompt_with_provider(
                model.model_key, request_text,
            )
        except Exception as exc:
            run = await self.run_repo.create(
                prompt_id=prompt.id, ai_model_id=model.id, request_text=request_text,
                status="failed", error_message=str(exc),
            )
            if source != "retry":
                await self.run_repo.release_daily_run(prompt.id, model.id, run_date)
            await self.run_repo.alert_run_failure(prompt.id, f"{getattr(model, 'name', model.model_key)} execution failed: {exc}")
            return [self._result(run, model, error=str(exc))]

        run = await self.run_repo.create(
            prompt_id=prompt.id, ai_model_id=model.id, request_text=request_text,
            response_text=response_text, status="success", provider_used=provider_used,
        )
        if source != "retry":
            await self.run_repo.complete_daily_run(prompt.id, model.id, run_date)
        try:
            extraction = await self.extraction_service.extract(response_text)
            saved = await self.persistence_service.persist(run.id, extraction)
            await self.run_repo.alert_new_competitor(prompt.id, [brand.name for brand in extraction.brands])
            await self.run_repo.alert_rank_changes(run.id)
            await self.run_repo.update_extraction(run, "completed")
            return [self._result(
                run, model, brands_found=len(extraction.brands),
                new_brands=saved.new_brands, existing_brands=saved.existing_brands,
            )]
        except Exception as exc:
            await self.run_repo.update_extraction(run, "failed", str(exc))
            return [self._result(run, model, error=str(exc))]

    async def retry_extraction(self, run_id: int, run_attempt: int = 1) -> None:
        run = await self.run_repo.get(run_id)
        if run is None or run.status != "success" or run.extraction_status == "completed" or not run.response_text:
            return
        try:
            extraction = await self.extraction_service.extract(run.response_text)
            saved = await self.persistence_service.persist(run.id, extraction)
            await self.run_repo.alert_new_competitor(run.prompt_id, [brand.name for brand in extraction.brands])
            await self.run_repo.alert_rank_changes(run.id)
            await self.run_repo.update_extraction(run, "completed")
        except Exception as exc:
            await self.run_repo.update_extraction(run, "failed", str(exc))

    @staticmethod
    def _result(run, model, *, brands_found=0, new_brands=0, existing_brands=0, error=None):
        return {
            "ai_run_id": run.id,
            "ai_run_status": run.status,
            "extraction_status": run.extraction_status,
            "brands_found": brands_found,
            "new_brands": new_brands,
            "existing_brands": existing_brands,
            "error_message": error,
        }
