import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.database.models import Prompt
from app.services.errors import AIProviderError, sanitize_body

logger = logging.getLogger(__name__)


def tehran_date(dt: datetime | None = None) -> date:
    """Return the Tehran calendar date for the given (or current) datetime."""
    tz = ZoneInfo(settings.RUN_TIMEZONE)
    if dt is None:
        return datetime.now(tz).date()
    return dt.astimezone(tz).date()


def _is_valid_answer(text: str) -> bool:
    """Last-resort guard. Primary classification is via AIProviderError."""
    if not text or not text.strip():
        return False
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            import json
            payload = json.loads(stripped)
            if isinstance(payload, dict) and "error" in payload and "choices" not in payload:
                return False
        except Exception:
            pass
    return True


def _public_error(exc: Exception) -> str:
    if isinstance(exc, AIProviderError):
        if exc.status is not None:
            return f"{exc.provider} HTTP {exc.status}"
        return f"{exc.provider} request failed"
    return "request failed"


class DailyModelRunService:
    def __init__(self, dmr_repo, run_repo, ai_service, extraction_service=None, persistence_service=None):
        self.dmr_repo = dmr_repo
        self.run_repo = run_repo
        self.ai_service = ai_service
        self.extraction_service = extraction_service
        self.persistence_service = persistence_service

    async def run_daily(self, prompt: Prompt, *, run_date: date, now: datetime | None = None, model_filter: list[str] | None = None) -> list[dict]:
        """Run all runnable models for the prompt on run_date, optionally filtered."""
        model_keys = [link.model.model_key for link in prompt.models if getattr(link.model, "is_active", True)]
        await self.dmr_repo.ensure_rows(prompt.id, model_keys, run_date)
        runnable = await self.dmr_repo.get_runnable(prompt.id, run_date, now=now)
        if model_filter is not None:
            runnable = [r for r in runnable if r.model in model_filter]
        return await self._execute_models(prompt, runnable, run_date, mode="auto")

    async def run_manual(self, prompt: Prompt, *, run_date: date, mode: str = "failed", now: datetime | None = None) -> list[dict]:
        """Manual rerun. mode='failed' resets retrying/exhausted; mode='all' resets all."""
        model_keys = [link.model.model_key for link in prompt.models if getattr(link.model, "is_active", True)]
        await self.dmr_repo.ensure_rows(prompt.id, model_keys, run_date)
        await self.dmr_repo.reset_for_manual(prompt.id, model_keys, run_date, mode=mode)
        runnable = await self.dmr_repo.get_runnable(prompt.id, run_date, now=now)
        return await self._execute_models(prompt, runnable, run_date, mode=mode)

    async def _execute_models(self, prompt: Prompt, runnable: list, run_date: date, mode: str = "auto") -> list[dict]:
        results = []
        for row in runnable:
            model_key = row.model
            link = next((l for l in prompt.models if l.model.model_key == model_key), None)
            if link is None:
                continue
            model = link.model

            locked = await self.dmr_repo.acquire_lock(prompt.id, model_key, run_date)
            if not locked:
                continue

            try:
                response_text, provider_used = await self.ai_service.run_prompt_with_provider(
                    model.model_key, prompt.text,
                )
                usage = getattr(self.ai_service, "last_usage", {})
                if not _is_valid_answer(response_text):
                    logger.warning("daily_model_run_last_resort_guard", extra={"event_data": {"model": model_key, "prompt_id": prompt.id}})
                    raise AIProviderError(provider_used or "primary", None, body="empty or error envelope answer")

                run = await self.run_repo.create(
                    prompt_id=prompt.id, ai_model_id=model.id, request_text=prompt.text,
                    response_text=response_text, status="success",
                    provider_used=provider_used, usage=usage,
                )
                await self.dmr_repo.mark_success(prompt.id, model_key, run_date, run.id)

                if self.extraction_service and self.persistence_service and response_text.strip():
                    try:
                        extraction = await self.extraction_service.extract(response_text)
                        saved = await self.persistence_service.persist(run.id, extraction)
                        await self.run_repo.alert_new_competitor(prompt.id, [b.name for b in extraction.brands])
                        await self.run_repo.alert_rank_changes(run.id)
                    except Exception as exc:
                        safe_ext = sanitize_body(str(exc))[:500]
                        if hasattr(self.run_repo, "update_extraction"):
                            await self.run_repo.update_extraction(run, "failed", safe_ext)

                results.append(self._model_result(model_key, "success", row.attempts + 1, None))
            except AIProviderError as exc:
                safe_msg = sanitize_body(str(exc))[:500]
                run = await self.run_repo.create(
                    prompt_id=prompt.id, ai_model_id=model.id, request_text=prompt.text,
                    status="failed", error_message=safe_msg,
                    error_provider=exc.provider, error_status=exc.status,
                    error_retryable=exc.retryable,
                )
                new_status = await self.dmr_repo.mark_failure(
                    prompt.id, model_key, run_date,
                    error_message=safe_msg,
                    error_provider=exc.provider,
                    error_status=exc.status,
                    error_retryable=exc.retryable,
                    retry_interval_minutes=settings.DAILY_RETRY_INTERVAL_MINUTES,
                )
                body_snippet = sanitize_body(exc.body)[:200]
                needs_fix = " needs manual fix" if exc.retryable is False else ""
                await self.run_repo.alert_run_failure(
                    prompt.id,
                    f"{getattr(model, 'name', model_key)} execution failed: "
                    f"provider={exc.provider} status={exc.status} body={body_snippet}{needs_fix}",
                )
                results.append(self._model_result(model_key, new_status, row.attempts + 1, _public_error(exc)))
            except Exception as exc:
                safe_msg = sanitize_body(str(exc))[:500]
                run = await self.run_repo.create(
                    prompt_id=prompt.id, ai_model_id=model.id, request_text=prompt.text,
                    status="failed", error_message=safe_msg,
                )
                new_status = await self.dmr_repo.mark_failure(
                    prompt.id, model_key, run_date,
                    error_message=safe_msg,
                    error_provider=None, error_status=None, error_retryable=None,
                    retry_interval_minutes=settings.DAILY_RETRY_INTERVAL_MINUTES,
                )
                results.append(self._model_result(model_key, new_status, row.attempts + 1, "request failed"))
            finally:
                await self.dmr_repo.release_lock(prompt.id, model_key, run_date)

        return results

    @staticmethod
    def _model_result(model: str, status: str, attempts: int, error: str | None) -> dict:
        return {
            "model": model,
            "status": status,
            "attempts": attempts,
            "last_error_public": error,
        }

    async def get_daily_status(self, prompt_id: int, run_date: date) -> dict:
        """Return per-model status for the prompt on run_date."""
        rows = await self.dmr_repo.get_rows(prompt_id, run_date)
        models = []
        failed_count = 0
        for r in rows:
            if r.status in ("retrying", "exhausted"):
                failed_count += 1
            models.append({
                "model": r.model,
                "status": r.status,
                "attempts": r.attempts,
                "last_error_public": self._safe_error_str(r),
                "next_attempt_at": r.next_attempt_at.isoformat() if r.next_attempt_at else None,
            })
        return {"models": models, "failed_count": failed_count}

    @staticmethod
    def _safe_error_str(row) -> str:
        if row.last_error_provider is not None and row.last_error_status is not None:
            return f"{row.last_error_provider} HTTP {row.last_error_status}"
        if row.last_error_provider is not None:
            return f"{row.last_error_provider} request failed"
        return "request failed" if row.status in ("retrying", "exhausted") else ""
