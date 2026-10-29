import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.database.models import Prompt
from app.infrastructure.run_queue import PromptRunJob, PromptRunQueue
from app.repositories.ai_run_repository import AIRunRepository
from app.repositories.system_settings_repository import (
    DOMAIN_INSTRUCTION_KEY,
    SystemSettingsRepository,
    get_setting,
)
from app.services.ai_service import AIService
from app.services.brand_extraction_service import BrandExtractionService
from app.services.brand_persistence_service import BrandPersistenceService
from app.services.errors import AIProviderError, sanitize_body

DOMAIN_FORMAT_INSTRUCTION = (
    "اگر نام برندی می‌آوری، دامنه رسمی آن را کنار نام به شکل «برند (example.com)» بنویس. "
    "دامنه را حدس نزن؛ اگر مطمئن نیستی، آن را نیاور. به این دستور در پاسخ اشاره نکن."
)
logger = logging.getLogger(__name__)
EXTRACTION_RETRY_DELAYS = (300, 900, 1800)

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
            try:
                results.extend(await self.run_prompt_model(prompt, link.model.id, now=now, source=source, run_attempt=run_attempt))
            except Exception as exc:
                logger.exception("prompt_model_run_failed", extra={"event_data": {"prompt_id": prompt.id, "ai_model_id": link.model.id, "error": str(exc)}})
        return results

    async def execution_availability(
        self, prompt: Prompt, *, now: datetime | None = None
    ) -> list[dict]:
        run_date = self._run_date(now)
        model_keys = [link.model.model_key for link in prompt.models]
        dmr_rows = await self._get_dmr_rows(prompt.id, run_date)
        dmr_map = {r.model: r for r in dmr_rows}
        result = [
            {
                "model_id": link.model.id,
                "model_name": link.model.name,
                "model_is_active": bool(getattr(link.model, "is_active", True)),
                "can_run": bool(getattr(link.model, "is_active", True)) and (
                    link.model.model_key not in dmr_map
                    or dmr_map[link.model.model_key].status in ("pending", "retrying")
                ),
                "claim_source": dmr_map.get(link.model.model_key).status if link.model.model_key in dmr_map else None,
            }
            for link in prompt.models
        ]
        logger.info("execution_availability_result", extra={"event_data": {"prompt_id": prompt.id, "models": [(r["model_name"], r["can_run"], r["claim_source"]) for r in result]}})
        return result

    async def _get_dmr_rows(self, prompt_id: int, run_date) -> list:
        try:
            from app.repositories.daily_model_run_repository import DailyModelRunRepository
            repo = DailyModelRunRepository(self.run_repo.session)
            rows = await repo.get_rows(prompt_id, run_date)
            logger.info("dmr_rows_loaded", extra={"event_data": {"prompt_id": prompt_id, "run_date": str(run_date), "count": len(rows)}})
            return rows
        except Exception as exc:
            logger.warning("dmr_rows_failed", extra={"event_data": {"prompt_id": prompt_id, "error": str(exc)}})
            return []

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
                usage = self.ai_service.last_usage
        except AIProviderError as exc:
            safe_msg = sanitize_body(str(exc))[:500]
            run = await self.run_repo.create(
                prompt_id=prompt.id, ai_model_id=model.id, request_text=request_text,
                status="failed", error_message=safe_msg,
                error_provider=exc.provider, error_status=exc.status, error_retryable=exc.retryable,
            )
            if source != "retry":
                await self.run_repo.release_daily_run(prompt.id, model.id, run_date)
            body_snippet = sanitize_body(exc.body)[:200]
            needs_fix = " needs manual fix" if exc.retryable is False else ""
            await self.run_repo.alert_run_failure(
                prompt.id,
                f"{getattr(model, 'name', model.model_key)} execution failed: "
                f"provider={exc.provider} status={exc.status} body={body_snippet}{needs_fix}",
            )
            await self._sync_dmr(prompt.id, model.model_key, run_date, "failed", error_provider=exc.provider, error_status=exc.status, error_retryable=exc.retryable)
            return [self._result(run, model, error=self._public_error(exc))]
        except Exception as exc:
            safe_msg = sanitize_body(str(exc))[:500]
            run = await self.run_repo.create(
                prompt_id=prompt.id, ai_model_id=model.id, request_text=request_text,
                status="failed", error_message=safe_msg,
            )
            if source != "retry":
                await self.run_repo.release_daily_run(prompt.id, model.id, run_date)
            await self.run_repo.alert_run_failure(prompt.id, f"{getattr(model, 'name', model.model_key)} execution failed: {safe_msg}")
            await self._sync_dmr(prompt.id, model.model_key, run_date, "failed")
            return [self._result(run, model, error="request failed")]

        run = await self.run_repo.create(
            prompt_id=prompt.id, ai_model_id=model.id, request_text=request_text,
            response_text=response_text, status="success", provider_used=provider_used, usage=usage,
        )
        if source != "retry":
            await self.run_repo.complete_daily_run(prompt.id, model.id, run_date)
        await self._sync_dmr(prompt.id, model.model_key, run_date, "success", run_id=run.id)
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
        except AIProviderError as exc:
            await self.run_repo.update_extraction(run, "failed", sanitize_body(str(exc))[:500])
            await self._schedule_extraction_retry(run, run_attempt)
            return [self._result(run, model, error=self._public_error(exc))]
        except Exception as exc:
            await self.run_repo.update_extraction(run, "failed", sanitize_body(str(exc))[:500])
            await self._schedule_extraction_retry(run, run_attempt)
            return [self._result(run, model, error="extraction failed")]

    async def _schedule_extraction_retry(self, run, run_attempt: int) -> None:
        if self.retry_queue is None or run_attempt > len(EXTRACTION_RETRY_DELAYS):
            return
        delay_seconds = EXTRACTION_RETRY_DELAYS[run_attempt - 1]
        job = PromptRunJob(
            prompt_id=run.prompt_id,
            ai_model_id=run.ai_model_id,
            run_date=self._run_date(getattr(run, "created_at", None)).isoformat(),
            source="extraction_retry",
            run_attempt=run_attempt + 1,
            ai_run_id=run.id,
        )
        try:
            await self.retry_queue.enqueue_extraction_retry(job, delay_seconds)
        except Exception:
            logger.exception("extraction_retry_enqueue_failed", extra={"event_data": {"ai_run_id": run.id, "run_attempt": run_attempt + 1}})

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
        except AIProviderError as exc:
            await self.run_repo.update_extraction(run, "failed", sanitize_body(str(exc))[:500])
            await self._schedule_extraction_retry(run, run_attempt)
        except Exception as exc:
            await self.run_repo.update_extraction(run, "failed", sanitize_body(str(exc))[:500])
            await self._schedule_extraction_retry(run, run_attempt)

    async def _sync_dmr(self, prompt_id: int, model_key: str, run_date, status: str, run_id: int | None = None, error_provider: str | None = None, error_status: int | None = None, error_retryable: bool | None = None) -> None:
        try:
            from app.repositories.daily_model_run_repository import DailyModelRunRepository
            repo = DailyModelRunRepository(self.run_repo.session)
            if status == "success" and run_id:
                await repo.mark_success(prompt_id, model_key, run_date, run_id)
            else:
                await repo.mark_failure(prompt_id, model_key, run_date,
                    error_provider=error_provider, error_status=error_status, error_retryable=error_retryable)
        except Exception:
            pass

    async def retry_failed_extractions(self, older_than_hours: int = 1) -> list[dict]:
        """Retry brand extraction for runs with failed extraction older than N hours."""
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        runs = await self.run_repo.get_failed_extractions(cutoff)
        results = []
        for run in runs:
            try:
                extraction = await self.extraction_service.extract(run.response_text)
                saved = await self.persistence_service.persist(run.id, extraction)
                await self.run_repo.alert_new_competitor(run.prompt_id, [b.name for b in extraction.brands])
                await self.run_repo.alert_rank_changes(run.id)
                await self.run_repo.update_extraction(run, "completed")
                results.append({"run_id": run.id, "status": "completed", "brands_found": len(extraction.brands)})
            except Exception as exc:
                safe_msg = sanitize_body(str(exc))[:500]
                await self.run_repo.update_extraction(run, "failed", safe_msg)
                results.append({"run_id": run.id, "status": "failed", "error": safe_msg})
        return results

    @staticmethod
    def _public_error(exc: AIProviderError) -> str:
        if exc.status is not None:
            return f"{exc.provider} HTTP {exc.status}"
        return f"{exc.provider} request failed"

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
