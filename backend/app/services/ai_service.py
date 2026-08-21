import asyncio
import json
import logging
import ssl
from urllib.parse import urlsplit

import aiohttp
import certifi

from app.core.config import settings
from app.observability import AI_DURATION, AI_REQUESTS, duration_seconds

logger = logging.getLogger(__name__)

AVALAI_MODEL_ALIASES = {
    "google/gemma-3-12b-it": "cf.gemma-3-12b-it",
    "meta-llama/llama-3.2-3b-instruct": "cf.llama-3.2-3b-instruct",
    "nvidia/nemotron-nano-12b-v2-vl": "nvidia_nim.nemotron-nano-12b-v2-vl",
    "qwen/qwen-3.7-plus": "qwen3.7-plus",
    "x-ai/grok-4-fast": "grok-4-fast-reasoning",
    "x-ai/grok-4.1-fast": "grok-4-1-fast-reasoning",
    "x-ai/grok-4.20": "grok-4.20-reasoning",
}
AVALAI_REASONING_GROK_MODELS = {
    "x-ai/grok-3-mini",
    "x-ai/grok-3-mini-beta",
    "x-ai/grok-4",
    "x-ai/grok-4-fast",
    "x-ai/grok-4.1-fast",
    "x-ai/grok-4.20",
    "x-ai/grok-4.20-multi-agent",
    "x-ai/grok-code-fast-1",
}


def avalai_model_key(model_key: str) -> str:
    if model_key in AVALAI_MODEL_ALIASES:
        return AVALAI_MODEL_ALIASES[model_key]
    model_id = model_key.rsplit("/", 1)[-1]
    return model_id.replace(".", "-") if model_id.startswith("claude-") else model_id


class AIService:
    _session: aiohttp.ClientSession | None = None

    @classmethod
    async def _get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=50)
            connector = aiohttp.TCPConnector(
                limit=100,
                ttl_dns_cache=300,
                ssl=ssl.create_default_context(cafile=certifi.where()),
            )
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
        response, _ = await self.run_prompt_with_provider(model_key, prompt_text, response_format)
        return response

    async def run_prompt_with_provider(
        self,
        model_key: str,
        prompt_text: str,
        response_format: dict | None = None,
    ) -> tuple[str, str]:
        base_url = settings.AI_GATEWAY_BASE_URL.rstrip("/")
        if response_format is None:
            endpoint = "/responses"
            payload = {
                "model": model_key,
                "input": prompt_text,
                "tools": [{"type": "web_search"}],
                "tool_choice": "auto",
                "include": ["web_search_call.action.sources"],
                "max_output_tokens": 5000,
            }
        else:
            endpoint = "/chat/completions"
            payload = {
                "model": model_key,
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": 0.7,
                "max_tokens": 5000,
            }
            payload["response_format"] = response_format

        try:
            body = await self._request(f"{base_url}/v1{endpoint}", payload, model_key)
            provider_used = "primary"
        except ValueError:
            if not settings.AVALAI_API_KEY:
                raise
            fallback_payload = {**payload, "model": avalai_model_key(model_key)}
            body = await self._request(
                f"{settings.AVALAI_BASE_URL.rstrip('/')}{endpoint}",
                fallback_payload,
                model_key,
                settings.AVALAI_API_KEY,
            )
            provider_used = "avalai"
        return self._normalize_response(body), provider_used

    async def _request(
        self,
        url: str,
        payload: dict,
        model_key: str,
        api_key: str = "",
    ) -> str:
        for attempt in range(3):
            started = __import__("time").perf_counter()
            try:
                session = await self._get_session()
                request_kwargs = {"json": payload}
                if api_key:
                    request_kwargs["headers"] = {"Authorization": f"Bearer {api_key}"}
                async with session.post(url, **request_kwargs) as response:
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

    @staticmethod
    def _normalize_response(body: str) -> str:
        try:
            payload = json.loads(body)
            sources: dict[str, None] = {}

            def add_source(url) -> None:
                if not isinstance(url, str):
                    return
                try:
                    parsed = urlsplit(url)
                except ValueError:
                    return
                if parsed.scheme in {"http", "https"} and parsed.netloc:
                    sources[url] = None

            if "output" in payload:
                parts = [
                    part
                    for item in payload["output"]
                    if item.get("type") == "message"
                    for part in item.get("content", [])
                ]
                for item in payload["output"]:
                    if item.get("type") == "web_search_call":
                        for source in item.get("action", {}).get("sources", []):
                            add_source(source.get("url"))
                for part in parts:
                    for annotation in part.get("annotations", []):
                        if annotation.get("type") == "url_citation":
                            add_source(annotation.get("url") or annotation.get("url_citation", {}).get("url"))
            elif "candidates" in payload:
                parts = payload["candidates"][0]["content"]["parts"]
                for candidate in payload["candidates"]:
                    for chunk in candidate.get("groundingMetadata", {}).get("groundingChunks", []):
                        add_source(chunk.get("web", {}).get("uri"))
            else:
                parts = payload["content"]
                for part in parts:
                    if part.get("type") == "web_search_tool_result":
                        for result in part.get("content", []):
                            add_source(result.get("url"))
                    for citation in part.get("citations", []):
                        add_source(citation.get("url"))
            text = "".join(
                part["text"] for part in parts
                if isinstance(part, dict)
                and isinstance(part.get("text"), str)
                and part.get("type") in (None, "text", "output_text")
            )
        except (TypeError, KeyError, IndexError, json.JSONDecodeError):
            return body
        if not text:
            return body
        normalized = {"choices": [{"message": {"content": text}}]}
        if sources:
            normalized["sources"] = list(sources)
        return json.dumps(normalized)

    @classmethod
    async def close(cls) -> None:
        if cls._session is not None:
            await cls._session.close()
            cls._session = None
