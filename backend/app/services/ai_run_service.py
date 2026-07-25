from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.database.models import Prompt
from app.repositories.ai_run_repository import AIRunRepository
from app.services.ai_service import AIService
from app.services.brand_extraction_service import BrandExtractionService
from app.services.brand_persistence_service import BrandPersistenceService

class AIRunService:
    def __init__(
        self,
        run_repo: AIRunRepository,
        ai_service: AIService,
        extraction_service: BrandExtractionService,
        persistence_service: BrandPersistenceService,
    ):
        self.run_repo = run_repo
        self.ai_service = ai_service
        self.extraction_service = extraction_service
        self.persistence_service = persistence_service

    @staticmethod
    def _run_date(now: datetime | None) -> date:
        timezone = ZoneInfo(settings.RUN_TIMEZONE)
        if now is None:
            return datetime.now(timezone).date()
        return (now.astimezone(timezone) if now.tzinfo else now).date()

    async def run_prompt_models(
        self, prompt: Prompt, *, now: datetime | None = None, source: str = "manual"
    ) -> list[dict]:
        results = []
        for link in prompt.models:
            results.extend(await self.run_prompt_model(prompt, link.model.id, now=now, source=source))
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
                "can_run": link.model.id not in claims,
                "claim_source": claims.get(link.model.id),
            }
            for link in prompt.models
        ]

    async def run_prompt_model(
        self, prompt: Prompt, ai_model_id: int, *, now: datetime | None = None, source: str = "manual"
    ) -> list[dict]:
        link = next((item for item in prompt.models if getattr(item, "ai_model_id", item.model.id) == ai_model_id), None)
        if link is None:
            return []
        model = link.model
        run_date = self._run_date(now)
        if source not in {"manual", "scheduled"}:
            raise ValueError("Invalid run source")
        if not await self.run_repo.claim_daily_run(prompt.id, model.id, run_date, source):
            return []
        request_text = prompt.text
        try:
            response_text = await self.ai_service.run_prompt(model.model_key, request_text)
        except Exception as exc:
            run = await self.run_repo.create(
                prompt_id=prompt.id, ai_model_id=model.id, request_text=request_text,
                status="failed", error_message=str(exc),
            )
            await self.run_repo.alert_run_failure(prompt.id, f"{getattr(model, 'name', model.model_key)} execution failed: {exc}")
            return [self._result(run, model, error=str(exc))]

        run = await self.run_repo.create(
            prompt_id=prompt.id, ai_model_id=model.id, request_text=request_text,
            response_text=response_text, status="success",
        )
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
