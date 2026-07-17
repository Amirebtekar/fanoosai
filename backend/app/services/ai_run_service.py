from datetime import datetime
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

    async def run_prompt_models(self, prompt: Prompt, *, now: datetime | None = None) -> list[dict]:
        results = []
        run_date = (now or datetime.now(ZoneInfo(settings.RUN_TIMEZONE))).date()
        for link in prompt.models:
            model = link.model
            if not await self.run_repo.claim_daily_run(prompt.id, model.id, run_date):
                continue
            request_text = prompt.text
            try:
                response_text = await self.ai_service.run_prompt(model.model_key, request_text)
            except Exception as exc:
                run = await self.run_repo.create(
                    prompt_id=prompt.id, ai_model_id=model.id, request_text=request_text,
                    status="failed", error_message=str(exc),
                )
                results.append(self._result(run, model, error=str(exc)))
                continue

            run = await self.run_repo.create(
                prompt_id=prompt.id, ai_model_id=model.id, request_text=request_text,
                response_text=response_text, status="success",
            )
            try:
                extraction = await self.extraction_service.extract(response_text)
                saved = await self.persistence_service.persist(run.id, extraction)
                await self.run_repo.update_extraction(run, "completed")
                results.append(self._result(
                    run, model, brands_found=len(extraction.brands),
                    new_brands=saved.new_brands, existing_brands=saved.existing_brands,
                ))
            except Exception as exc:
                await self.run_repo.update_extraction(run, "failed", str(exc))
                results.append(self._result(run, model, error=str(exc)))
        return results

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
