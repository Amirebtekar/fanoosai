import asyncio
import logging

import aiohttp

from app.core.config import settings
from app.observability import AI_DURATION, AI_REQUESTS, duration_seconds

logger = logging.getLogger(__name__)


class AIService:
    _session: aiohttp.ClientSession | None = None

    @classmethod
    async def _get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=50)
            connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            if settings.AI_GATEWAY_API_KEY:
                headers["Authorization"] = f"Bearer {settings.AI_GATEWAY_API_KEY}"
            cls._session = aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers)
        return cls._session

    async def run_prompt(
        self,
        model_key: str,
        prompt_text: str,
        response_format: dict | None = None,
    ) -> str:
        url = f"{settings.AI_GATEWAY_BASE_URL.rstrip('/')}/v1/chat/completions"
        payload = {
            "model": model_key,
            "messages": [{"role": "user", "content": prompt_text}],
            "temperature": 0.7,
            "max_tokens": 5000,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        for attempt in range(3):
            started = __import__("time").perf_counter()
            try:
                session = await self._get_session()
                async with session.post(url, json=payload) as response:
                    body = await response.text()
                    if response.status >= 500 or response.status == 429:
                        raise aiohttp.ClientResponseError(
                            response.request_info, response.history,
                            status=response.status, message="retryable provider response",
                        )
                    if response.status >= 400:
                        AI_REQUESTS.labels(model_key, "error").inc()
                        raise ValueError("AI Gateway request failed")
                    AI_REQUESTS.labels(model_key, "success").inc()
                    return body
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                if attempt == 2:
                    AI_REQUESTS.labels(model_key, "error").inc()
                    logger.exception("ai_provider_request_failed", extra={"event_data": {"provider": model_key}})
                    raise ValueError("AI Gateway request failed after retries") from exc
                await asyncio.sleep(2**attempt)
            finally:
                AI_DURATION.labels(model_key).observe(duration_seconds(started))
        raise ValueError("AI Gateway request failed")

    @classmethod
    async def close(cls) -> None:
        if cls._session is not None:
            await cls._session.close()
            cls._session = None
