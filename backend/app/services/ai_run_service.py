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


class _RunRef:
    """Minimal run handle (id only) for status updates without loading ORM state."""

    __slots__ = ("id", "extraction_status", "extraction_error", "processed_at")

    def __init__(self, run_id: int):
        self.id = run_id
        self.extraction_status = None
        self.extraction_error = None
        self.processed_at = None

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
        dmr_rows = await self._get_dmr_rows(prompt.id, run_date)
        dmr_map = {r.model: r for r in dmr_rows}
        claims = await self._get_claim_sources(prompt.id, [link.model.id for link in prompt.models], run_date)
        result = []
        for link in prompt.models:
            is_active = bool(getattr(link.model, "is_active", True))
            row = dmr_map.get(link.model.model_key)
            if row is not None:
                can_run = row.status in ("pending", "retrying")
                claim_source = row.status
            else:
                claim_source = claims.get(link.model.id)
                can_run = claim_source is None
            result.append({
                "model_id": link.model.id,
                "model_name": link.model.name,
                "model_is_active": is_active,
                "can_run": is_active and can_run,
                "claim_source": claim_source,
            })
        logger.info("execution_availability_result", extra={"event_data": {"prompt_id": prompt.id, "models": [(r["model_name"], r["can_run"], r["claim_source"]) for r in result]}})
        return result

    async def _get_claim_sources(self, prompt_id: int, model_ids: list[int], run_date) -> dict:
        try:
            return await self.run_repo.get_daily_claim_sources(prompt_id, model_ids, run_date)
        except Exception as exc:
            logger.warning("daily_claims_failed", extra={"event_data": {"prompt_id": prompt_id, "error": str(exc)}})
            return {}

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

        prompt_id = prompt.id
        model_id = model.id
        model_key = model.model_key
        run = await self.run_repo.create(
            prompt_id=prompt_id, ai_model_id=model_id, request_text=request_text,
            response_text=response_text, status="success", provider_used=provider_used, usage=usage,
        )
        if source != "retry":
            await self.run_repo.complete_daily_run(prompt_id, model_id, run_date)
        await self._sync_dmr(prompt_id, model_key, run_date, "success", run_id=run.id)
        try:
            extraction = await self.extraction_service.extract(response_text)
            saved = await self.persistence_service.persist(run.id, extraction)
        except AIProviderError as exc:
            await self._mark_extraction(run, "failed", sanitize_body(str(exc))[:500])
            await self._schedule_extraction_retry(run, run_attempt)
            return [self._result(run, model, error=self._public_error(exc))]
        except Exception as exc:
            await self._mark_extraction(run, "failed", sanitize_body(str(exc))[:500])
            await self._schedule_extraction_retry(run, run_attempt)
            return [self._result(run, model, error="extraction failed")]
        await self._mark_extraction(run, "completed")
        await self._send_brand_alerts(prompt_id, run.id, extraction)
        return [self._result(
            run, model, brands_found=len(extraction.brands),
            new_brands=saved.new_brands, existing_brands=saved.existing_brands,
        )]

    async def _mark_extraction(self, run, status: str, error: str | None = None) -> None:
        try:
            await self.run_repo.update_extraction(run, status, error)
        except Exception:
            logger.exception("extraction_status_update_failed", extra={"event_data": {"status": status}})
            await self._safe_rollback()

    async def _send_brand_alerts(self, prompt_id: int, run_id: int, extraction) -> None:
        try:
            await self.run_repo.alert_new_competitor(prompt_id, [brand.name for brand in extraction.brands])
            await self.run_repo.alert_rank_changes(run_id)
        except Exception:
            logger.exception("brand_alerts_failed", extra={"event_data": {"ai_run_id": run_id}})
            await self._safe_rollback()

    async def _safe_rollback(self) -> None:
        session = getattr(self.run_repo, "session", None)
        if session is None:
            return
        try:
            await session.rollback()
        except Exception:
            logger.exception("session_rollback_failed")

    async def _schedule_extraction_retry(self, run, run_attempt: int) -> None:
        if self.retry_queue is None or run_attempt > len(EXTRACTION_RETRY_DELAYS):
            return
        delay_seconds = EXTRACTION_RETRY_DELAYS[run_attempt - 1]
        try:
            job = PromptRunJob(
                prompt_id=run.prompt_id,
                ai_model_id=run.ai_model_id,
                run_date=self._run_date(getattr(run, "created_at", None)).isoformat(),
                source="extraction_retry",
                run_attempt=run_attempt + 1,
                ai_run_id=run.id,
            )
            await self.retry_queue.enqueue_extraction_retry(job, delay_seconds)
        except Exception:
            logger.exception("extraction_retry_enqueue_failed", extra={"event_data": {"run_attempt": run_attempt + 1}})

    async def retry_extraction(self, run_id: int, run_attempt: int = 1) -> None:
        run = await self.run_repo.get(run_id)
        if run is None or run.status != "success" or run.extraction_status == "completed" or not run.response_text:
            return
        prompt_id = run.prompt_id
        try:
            extraction = await self.extraction_service.extract(run.response_text)
            await self.persistence_service.persist(run_id, extraction)
        except Exception as exc:
            await self._mark_extraction(run, "failed", sanitize_body(str(exc))[:500])
            await self._schedule_extraction_retry(run, run_attempt)
            return
        await self._mark_extraction(run, "completed")
        await self._send_brand_alerts(prompt_id, run_id, extraction)

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

    async def retry_failed_extractions(
        self,
        older_than_hours: float = 1,
        *,
        prompt_id: int | None = None,
        limit: int | None = None,
        max_attempts: int | None = None,
        backoff_minutes: float | None = None,
        alerts: bool = True,
    ) -> list[dict]:
        """Retry brand extraction for successful runs whose extraction failed.

        Bounded on purpose: at most ``limit`` runs per call, each run at most
        ``max_attempts`` times, and never again within ``backoff_minutes`` of its last
        attempt. Each run is isolated, so one bad run cannot stop the batch.
        """
        from datetime import timedelta, timezone

        now = datetime.now(timezone.utc)
        max_attempts = settings.EXTRACTION_MAX_ATTEMPTS if max_attempts is None else max_attempts
        backoff_minutes = settings.EXTRACTION_RETRY_BACKOFF_MINUTES if backoff_minutes is None else backoff_minutes
        limit = settings.EXTRACTION_RETRY_BATCH_SIZE if limit is None else limit
        if limit <= 0:
            return []  # a zero batch size disables automatic retries
        candidates = await self.run_repo.get_failed_extractions(
            now - timedelta(hours=older_than_hours),
            prompt_id=prompt_id,
            max_attempts=max_attempts if max_attempts > 0 else None,
            retry_before=now - timedelta(minutes=backoff_minutes) if backoff_minutes > 0 else None,
            limit=limit,
        )
        results = []
        for run_id, run_prompt_id, response_text in candidates:
            run_ref = _RunRef(run_id)
            try:
                extraction = await self.extraction_service.extract(response_text)
                saved = await self.persistence_service.persist(run_id, extraction)
            except Exception as exc:
                safe_msg = sanitize_body(str(exc))[:500]
                logger.warning("extraction_retry_failed", extra={"event_data": {"ai_run_id": run_id, "error": safe_msg[:300]}})
                await self._mark_extraction(run_ref, "failed", safe_msg)
                results.append({"run_id": run_id, "status": "failed", "error": safe_msg})
                continue
            await self._mark_extraction(run_ref, "completed")
            if alerts:
                await self._send_brand_alerts(run_prompt_id, run_id, extraction)
            results.append({
                "run_id": run_id, "status": "completed", "brands_found": len(extraction.brands),
                "saved_brands": getattr(saved, "run_brands", None), "skipped_brands": getattr(saved, "skipped_brands", 0),
            })
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
