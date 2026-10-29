import asyncio
import json
import logging
import math
import random
import re
import ssl
import time
from urllib.parse import urlsplit

import aiohttp
import certifi

from app.core.config import settings
from app.observability import AI_DURATION, AI_REQUESTS, duration_seconds
from app.services.errors import AIProviderError

logger = logging.getLogger(__name__)

_ERROR_BODY_READ_LIMIT = 64 * 1024
_RETRY_JITTER_RATIO = 0.2

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


_METADATA_MAX_ITEMS = 200
_METADATA_MAX_TEXT = 2048
_RESPONSE_BODY_KEYS = ("output", "choices", "candidates", "content")


def _safe_url(value) -> str | None:
    if not isinstance(value, str):
        return None
    url = value.strip()
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if parsed.scheme in {"http", "https"} and parsed.netloc and len(url) <= _METADATA_MAX_TEXT:
        return url
    return None


def _clean_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:_METADATA_MAX_TEXT] if text else None


def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _integer(value) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _first(*values):
    return next((value for value in values if value is not None), None)


def _decode_json_object(text: str) -> dict | None:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(stripped)
    except (json.JSONDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _decode_sse_payload(text: str) -> dict | None:
    """Rebuild one payload from SSE frames: a final Responses object, else the last usage seen."""
    merged: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        frame = _decode_json_object(line[5:])
        if frame is None:
            continue
        if isinstance(frame.get("response"), dict) and frame.get("type") in ("response.completed", "response.done"):
            return frame["response"]
        for key in ("usage", "estimated_cost", "tool_usage"):
            if isinstance(frame.get(key), dict):
                merged[key] = frame[key]
    return merged or None


def extract_response_metadata(raw_body) -> dict:
    """Usage, cost and web-search details of one provider body; never raises."""
    result: dict = {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "reasoning_tokens": None,
        "cached_tokens": None,
        "cost_irt": None,
        "cost_usd": None,
        "web_search_count": None,
        "web_search_queries": [],
        "web_search_actions": [],
        "citations": [],
    }
    queries: dict[str, None] = {}
    citations: dict[str, dict] = {}

    def add_query(value) -> None:
        query = _clean_text(value)
        if query and len(queries) < _METADATA_MAX_ITEMS:
            queries[query] = None
            result["web_search_queries"] = list(queries)

    def add_action(action: dict) -> None:
        if len(result["web_search_actions"]) < _METADATA_MAX_ITEMS:
            result["web_search_actions"].append(action)

    def add_citation(url, title=None) -> None:
        safe = _safe_url(url)
        if safe is None:
            return
        clean_title = _clean_text(title)
        if safe in citations:
            if citations[safe]["title"] is None and clean_title:
                citations[safe]["title"] = clean_title
        elif len(citations) < _METADATA_MAX_ITEMS:
            citations[safe] = {"url": safe, "title": clean_title}
        result["citations"] = list(citations.values())

    try:
        if isinstance(raw_body, (bytes, bytearray)):
            raw_body = bytes(raw_body).decode("utf-8", errors="replace")
        if not isinstance(raw_body, str):
            return result
        outer = _decode_json_object(raw_body)
        if outer is None:
            payload = _decode_sse_payload(raw_body)
            if payload is None:
                return result
            outer = payload
        else:
            payload = _decode_json_object(AIService._unwrap_gateway_body(raw_body)) or outer
            inner = payload.get("data")
            if isinstance(inner, dict) and not any(key in payload for key in _RESPONSE_BODY_KEYS):
                payload = inner
        containers = [payload] if payload is outer else [payload, outer]

        def lookup(key: str) -> dict:
            return next((container[key] for container in containers if isinstance(container.get(key), dict)), {})

        usage = lookup("usage")
        gemini_usage = lookup("usageMetadata")
        input_details = _dict(usage.get("input_tokens_details")) or _dict(usage.get("prompt_tokens_details"))
        output_details = _dict(usage.get("output_tokens_details")) or _dict(usage.get("completion_tokens_details"))
        result["prompt_tokens"] = _integer(_first(usage.get("input_tokens"), usage.get("prompt_tokens"), gemini_usage.get("promptTokenCount")))
        result["completion_tokens"] = _integer(_first(usage.get("output_tokens"), usage.get("completion_tokens"), gemini_usage.get("candidatesTokenCount")))
        total = _integer(_first(usage.get("total_tokens"), gemini_usage.get("totalTokenCount")))
        if total is None and result["prompt_tokens"] is not None and result["completion_tokens"] is not None:
            total = result["prompt_tokens"] + result["completion_tokens"]
        result["total_tokens"] = total
        result["reasoning_tokens"] = _integer(_first(output_details.get("reasoning_tokens"), gemini_usage.get("thoughtsTokenCount")))
        result["cached_tokens"] = _integer(_first(
            input_details.get("cached_tokens"), usage.get("cache_read_input_tokens"), gemini_usage.get("cachedContentTokenCount"),
        ))

        cost = lookup("estimated_cost")
        result["cost_irt"] = _number(cost.get("irt"))
        result["cost_usd"] = _number(cost.get("unit"))
        reported_searches = _integer(_first(
            _dict(lookup("tool_usage").get("web_search")).get("num_requests"),
            _dict(usage.get("server_tool_use")).get("web_search_requests"),
        ))
        result["web_search_count"] = reported_searches

        counted_searches: int | None = None
        output = payload.get("output")
        if isinstance(output, list):
            counted_searches = 0
            for item in output:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "web_search_call":
                    action = _dict(item.get("action"))
                    action_type = action.get("type") if isinstance(action.get("type"), str) else None
                    item_queries = [query for query in (_clean_text(value) for value in _list(action.get("queries"))) if query]
                    single_query = _clean_text(action.get("query"))
                    if action_type == "search" or (action_type is None and (item_queries or single_query)):
                        counted_searches += 1
                        for query in item_queries or [single_query]:
                            add_query(query)
                        compact: dict = {"type": "search"}
                        if item_queries:
                            compact["queries"] = item_queries[:_METADATA_MAX_ITEMS]
                        elif single_query:
                            compact["query"] = single_query
                        sources = list(dict.fromkeys(
                            url for url in (_safe_url(_dict(source).get("url")) for source in _list(action.get("sources"))) if url
                        ))
                        if sources:
                            compact["sources"] = sources[:_METADATA_MAX_ITEMS]
                        add_action(compact)
                    elif action_type is not None:
                        compact = {"type": _clean_text(action_type) or "unknown"}
                        url = _safe_url(action.get("url"))
                        if url:
                            compact["url"] = url
                        pattern = _clean_text(action.get("pattern"))
                        if pattern:
                            compact["pattern"] = pattern
                        add_action(compact)
                elif item.get("type") == "message":
                    for part in _list(item.get("content")):
                        for annotation in _list(_dict(part).get("annotations")):
                            annotation = _dict(annotation)
                            if annotation.get("type") == "url_citation":
                                nested = _dict(annotation.get("url_citation"))
                                add_citation(annotation.get("url") or nested.get("url"), annotation.get("title") or nested.get("title"))

        for choice in _list(payload.get("choices"))[:1]:
            message = _dict(_dict(choice).get("message"))
            for annotation in _list(message.get("annotations")):
                annotation = _dict(annotation)
                nested = _dict(annotation.get("url_citation"))
                add_citation(nested.get("url") or annotation.get("url"), nested.get("title") or annotation.get("title"))

        content = payload.get("content")
        if isinstance(content, list):
            anthropic_searches = 0
            for part in content:
                part = _dict(part)
                part_type = part.get("type")
                tool_input = _dict(part.get("input"))
                if part_type == "server_tool_use" and part.get("name") == "web_search":
                    anthropic_searches += 1
                    query = _clean_text(tool_input.get("query"))
                    add_query(query)
                    add_action({"type": "search", "query": query} if query else {"type": "search"})
                elif part_type == "server_tool_use" and part.get("name") == "web_fetch":
                    url = _safe_url(tool_input.get("url"))
                    add_action({"type": "open_page", "url": url} if url else {"type": "open_page"})
                elif part_type == "web_search_tool_result":
                    for entry in _list(part.get("content")):
                        entry = _dict(entry)
                        add_citation(entry.get("url"), entry.get("title"))
                for citation in _list(part.get("citations")):
                    citation = _dict(citation)
                    add_citation(citation.get("url"), citation.get("title"))
            if anthropic_searches:
                counted_searches = (counted_searches or 0) + anthropic_searches

        for candidate in _list(payload.get("candidates")):
            grounding = _dict(_dict(candidate).get("groundingMetadata"))
            gemini_queries = [query for query in (_clean_text(value) for value in _list(grounding.get("webSearchQueries"))) if query]
            if gemini_queries:
                for query in gemini_queries:
                    add_query(query)
                add_action({"type": "search", "queries": gemini_queries[:_METADATA_MAX_ITEMS]})
                counted_searches = (counted_searches or 0) + len(gemini_queries)
            for chunk in _list(grounding.get("groundingChunks")):
                web = _dict(_dict(chunk).get("web"))
                add_citation(web.get("uri"), web.get("title"))

        if result["web_search_count"] is None:
            result["web_search_count"] = counted_searches
    except Exception:
        logger.debug("ai_response_metadata_parse_failed", exc_info=True)
    return result


class AIService:
    _session: aiohttp.ClientSession | None = None
    last_usage: dict

    def __init__(self) -> None:
        self.last_usage = {}
        self._response_metadata: dict = {}

    @classmethod
    async def _get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            timeout = aiohttp.ClientTimeout(total=180, connect=15, sock_read=150)
            connector = aiohttp.TCPConnector(
                limit=100,
                ttl_dns_cache=300,
                ssl=ssl.create_default_context(cafile=certifi.where()),
            )
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }
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
        self.last_usage = {}
        self._response_metadata = {}
        deadline_seconds = settings.AI_TOTAL_DEADLINE_SECONDS or settings.RUN_CLAIM_LEASE_SECONDS * 0.5
        deadline = time.monotonic() + deadline_seconds
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
            }
            payload["response_format"] = response_format

        primary_error: AIProviderError | None = None
        if settings.AI_GATEWAY_ENABLED:
            try:
                body = await self._request_with_retry(f"{base_url}/v1{endpoint}", payload, model_key, provider="primary", deadline=deadline)
                self.last_usage = getattr(self, "_response_metadata", None) or self._usage(body)
                return body, "primary"
            except AIProviderError as exc:
                primary_error = exc

        if not settings.AVALAI_API_KEY:
            raise ValueError("No AI provider enabled")
        remaining = deadline - time.monotonic()
        if remaining <= 5:
            combined = f"{primary_error} | fallback skipped: total deadline exceeded"
            raise AIProviderError("fallback", None, body=combined, primary_error=primary_error) from primary_error
        fallback_payload = {
            "model": settings.AVALAI_MODEL or avalai_model_key(model_key),
            "messages": [{"role": "user", "content": prompt_text}],
            "temperature": 0.7,
        }
        if response_format is not None:
            fallback_payload["response_format"] = response_format
        try:
            body = await self._request_with_retry(
                f"{settings.AVALAI_BASE_URL.rstrip('/')}/chat/completions",
                fallback_payload,
                model_key,
                settings.AVALAI_API_KEY,
                provider="fallback",
                deadline=deadline,
            )
        except AIProviderError as fallback_error:
            if primary_error is not None:
                combined = f"{primary_error} | {fallback_error}"
                raise AIProviderError(
                    fallback_error.provider,
                    fallback_error.status,
                    body=combined,
                    cause=fallback_error.cause,
                    primary_error=primary_error,
                    fallback_error=fallback_error,
                ) from primary_error
            raise
        self.last_usage = getattr(self, "_response_metadata", None) or self._usage(body)
        return body, "9router"

    async def _request_with_retry(
        self,
        url: str,
        payload: dict,
        model_key: str,
        api_key: str = "",
        provider: str = "primary",
        deadline: float | None = None,
    ) -> str:
        last_error: AIProviderError | None = None
        max_attempts = settings.AI_MAX_RETRIES + 1
        base_delay = settings.AI_RETRY_BASE_DELAY
        for attempt in range(max_attempts):
            if attempt > 0:
                delay = base_delay * (2 ** (attempt - 1))
                jitter = 1.0 + random.uniform(-_RETRY_JITTER_RATIO, _RETRY_JITTER_RATIO)
                sleep_time = delay * jitter
                if deadline is not None and time.monotonic() + sleep_time >= deadline:
                    raise AIProviderError(provider, None, body="total deadline exceeded", synthetic=True) from last_error
                await asyncio.sleep(sleep_time)
            remaining = None
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AIProviderError(provider, None, body="total deadline exceeded", synthetic=True)
            timeout = None
            if remaining is not None:
                timeout = aiohttp.ClientTimeout(total=min(180, remaining))
            try:
                return await self._request(url, payload, model_key, api_key, provider=provider, timeout=timeout)
            except AIProviderError as exc:
                last_error = exc
                if not exc.retryable:
                    raise
        raise last_error

    @staticmethod
    def _unwrap_gateway_body(body: str) -> str:
        text = body.strip()
        if not text.startswith("{"):
            return body
        try:
            payload, _ = json.JSONDecoder().raw_decode(text)
        except json.JSONDecodeError:
            return body
        if isinstance(payload, dict):
            inner = payload.get("data")
            if isinstance(inner, dict) and ("choices" in inner or "output" in inner):
                return json.dumps(inner)
        return body

    @staticmethod
    def _usage(body: str) -> dict:
        try:
            payload = json.loads(body)
            usage = payload.get("usage") or {}
            cost = payload.get("estimated_cost") or {}
            return {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
                "cost_irt": cost.get("irt"),
            }
        except (TypeError, json.JSONDecodeError):
            return {}

    async def _request(
        self,
        url: str,
        payload: dict,
        model_key: str,
        api_key: str = "",
        provider: str = "primary",
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> str:
        started = time.perf_counter()
        host = urlsplit(url).netloc
        try:
            session = await self._get_session()
            request_kwargs = {"json": payload}
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            request_kwargs["headers"] = headers
            if timeout is not None:
                request_kwargs["timeout"] = timeout
            async with session.post(url, **request_kwargs) as response:
                if response.status >= 400:
                    try:
                        body = (await response.text())[:_ERROR_BODY_READ_LIMIT]
                    except Exception:
                        body = ""
                    AI_REQUESTS.labels(model_key, "error").inc()
                    logger.warning(
                        "ai_provider_http_error",
                        extra={"event_data": {
                            "provider": provider,
                            "status": response.status,
                            "model": model_key,
                            "host": host,
                        }},
                    )
                    raise AIProviderError(provider, response.status, body)
                body = await response.text()
                AI_REQUESTS.labels(model_key, "success").inc()
                unwrapped = self._unwrap_gateway_body(body)
                normalized = self._normalize_response(unwrapped, provider=provider)
                self._response_metadata = extract_response_metadata(body)
                return normalized
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            AI_REQUESTS.labels(model_key, "error").inc()
            logger.warning(
                "ai_provider_request_failed",
                extra={"event_data": {
                    "provider": provider,
                    "model": model_key,
                    "host": host,
                    "error_type": type(exc).__name__,
                }},
            )
            raise AIProviderError(provider, None, cause=exc) from exc
        finally:
            AI_DURATION.labels(model_key).observe(duration_seconds(started))

    @staticmethod
    def _parse_retry_after(message: str) -> int | None:
        m = re.search(r"reset after\s+(\d+)\s*m\s*(\d+)\s*s", message)
        if m:
            return int(m.group(1)) * 60 + int(m.group(2))
        m = re.search(r"reset after\s+(\d+)\s*s", message)
        if m:
            return int(m.group(1))
        m = re.search(r"reset after\s+(\d+)\s*m", message)
        if m:
            return int(m.group(1)) * 60
        return None

    @staticmethod
    def _error_envelope_to_exception(payload: dict, provider: str, http_status: int | None = None, content_type: str | None = None) -> AIProviderError:
        raw = payload.get("error")
        if isinstance(raw, str):
            message = raw
            embedded_code = None
        elif isinstance(raw, dict):
            message = str(raw.get("message", ""))
            code = raw.get("code")
            embedded_code = code if isinstance(code, int) else None
        else:
            message = str(raw)
            embedded_code = None

        embedded_status = None
        m = re.search(r"\[(\d{3})\]", message)
        if m:
            embedded_status = int(m.group(1))
        elif embedded_code is not None:
            embedded_status = embedded_code
        elif http_status is not None:
            embedded_status = http_status

        msg_lower = message.lower()
        has_reset = any(kw in msg_lower for kw in ("reset after", "rate limit", "quota"))

        if embedded_status is not None:
            if embedded_status in (400, 401, 403, 404):
                retryable = has_reset and embedded_status == 429
            elif embedded_status in (408, 425, 429):
                retryable = True
            elif embedded_status >= 500:
                retryable = True
            else:
                retryable = has_reset
        else:
            retryable = True if has_reset else True

        retry_after = AIService._parse_retry_after(message)

        logger.warning(
            "ai_provider_error_envelope",
            extra={"event_data": {
                "provider": provider,
                "embedded_status": embedded_status,
                "http_status": http_status,
                "content_type": content_type,
                "model": "unknown",
            }},
        )

        err = AIProviderError(provider, embedded_status, body=message)
        err.retryable = retryable
        err.retry_after_seconds = retry_after
        return err

    @staticmethod
    def _try_sse(body: str, provider: str) -> str | None:
        """Try to parse SSE data lines with JSON deltas. Returns assembled text or None."""
        text_parts = []
        for line in body.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                continue
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            if "error" in obj:
                raise AIService._error_envelope_to_exception(obj, provider)
            choices = obj.get("choices") or []
            for ch in choices:
                delta = ch.get("delta") or {}
                content = delta.get("content")
                if isinstance(content, str):
                    text_parts.append(content)
                msg = ch.get("message") or {}
                mc = msg.get("content")
                if isinstance(mc, str):
                    text_parts.append(mc)
        if text_parts:
            return "".join(text_parts)
        return None

    @staticmethod
    def _raise_empty(provider: str, http_status: int | None = None, content_type: str | None = None, model: str = "unknown") -> None:
        logger.warning(
            "ai_provider_empty_or_unrecognized",
            extra={"event_data": {
                "provider": provider,
                "http_status": http_status,
                "content_type": content_type,
                "model": model,
            }},
        )
        raise AIProviderError(provider, None, body="empty or unrecognized response from provider")

    @staticmethod
    def _normalize_response(body: str, provider: str = "primary", http_status: int | None = None, content_type: str | None = None) -> str:
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            sse_text = AIService._try_sse(body, provider)
            if sse_text is not None:
                normalized = {"choices": [{"message": {"content": sse_text}}]}
                return json.dumps(normalized)
            AIService._raise_empty(provider, http_status=http_status, content_type=content_type)

        if not isinstance(payload, dict):
            AIService._raise_empty(provider, http_status=http_status, content_type=content_type)

        if "error" in payload:
            raise AIService._error_envelope_to_exception(payload, provider, http_status=http_status, content_type=content_type)

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

        text = ""
        if "output" in payload:
            output_items = payload.get("output") or []
            if not output_items:
                AIService._raise_empty(provider, http_status=http_status, content_type=content_type)
            parts = [
                part
                for item in output_items
                if isinstance(item, dict) and item.get("type") == "message"
                for part in (item.get("content") or [])
                if isinstance(part, dict)
            ]
            for item in output_items:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "web_search_call":
                    action = item.get("action") or {}
                    if not isinstance(action, dict):
                        continue
                    for source in action.get("sources") or []:
                        if isinstance(source, dict):
                            add_source(source.get("url"))
            for part in parts:
                for annotation in part.get("annotations") or []:
                    if not isinstance(annotation, dict):
                        continue
                    if annotation.get("type") == "url_citation":
                        add_source(annotation.get("url") or annotation.get("url_citation", {}).get("url"))
            text = "".join(
                part["text"] for part in parts
                if isinstance(part, dict)
                and isinstance(part.get("text"), str)
                and part.get("type") in (None, "text", "output_text")
            )
        elif "candidates" in payload:
            candidates = payload.get("candidates") or []
            if not candidates:
                AIService._raise_empty(provider, http_status=http_status, content_type=content_type)
            try:
                parts = candidates[0]["content"]["parts"]
            except (KeyError, TypeError, IndexError):
                AIService._raise_empty(provider, http_status=http_status, content_type=content_type)
            for candidate in candidates:
                for chunk in candidate.get("groundingMetadata", {}).get("groundingChunks", []):
                    add_source(chunk.get("web", {}).get("uri"))
            text = "".join(
                part["text"] for part in parts
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
        elif "choices" in payload:
            choices = payload.get("choices") or []
            if not choices:
                AIService._raise_empty(provider, http_status=http_status, content_type=content_type)
            message = choices[0].get("message") or {}
            text = message.get("content") if isinstance(message.get("content"), str) else ""
            for url in re.findall(r"https?://[^\s)\]>]+", text):
                add_source(url.rstrip(".,;:!?\"'"))
            if not text or not text.strip():
                AIService._raise_empty(provider, http_status=http_status, content_type=content_type)
            normalized = {"choices": [{"message": {"content": text}}]}
            if sources:
                normalized["sources"] = list(sources)
            return json.dumps(normalized)
        elif "content" in payload:
            parts = payload.get("content") or []
            if not parts:
                AIService._raise_empty(provider, http_status=http_status, content_type=content_type)
            for part in parts:
                if not isinstance(part, dict):
                    continue
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
        else:
            AIService._raise_empty(provider, http_status=http_status, content_type=content_type)

        if not text or not text.strip():
            AIService._raise_empty(provider, http_status=http_status, content_type=content_type)

        normalized = {"choices": [{"message": {"content": text}}]}
        if sources:
            normalized["sources"] = list(sources)
        return json.dumps(normalized)

    @classmethod
    async def close(cls) -> None:
        if cls._session is not None:
            await cls._session.close()
            cls._session = None
