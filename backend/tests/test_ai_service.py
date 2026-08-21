import json
import ssl
from types import SimpleNamespace

import pytest

import app.services.ai_service as ai_service_module
from app.services.ai_service import AIService


@pytest.mark.asyncio
async def test_session_uses_a_verified_certifi_tls_context(monkeypatch):
    captured = {}

    class Connector:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class Session:
        closed = False

        async def close(self):
            pass

    monkeypatch.setattr(ai_service_module.aiohttp, "TCPConnector", Connector)
    monkeypatch.setattr(ai_service_module.aiohttp, "ClientSession", lambda **kwargs: Session())
    AIService._session = None

    await AIService._get_session()

    assert captured["ssl"].verify_mode == ssl.CERT_REQUIRED
    await AIService.close()


def test_normalizes_gemini_response_to_openai_choices_shape():
    response = AIService._normalize_response(json.dumps({
        "candidates": [{
            "content": {"parts": [{"text": "ابر آروان (arvancloud.ir)"}]},
            "groundingMetadata": {
                "groundingChunks": [{"web": {"uri": "https://example.com/gemini-source"}}],
            },
        }],
    }))

    assert json.loads(response) == {
        "choices": [{"message": {"content": "ابر آروان (arvancloud.ir)"}}],
        "sources": ["https://example.com/gemini-source"],
    }


def test_normalizes_claude_response_to_openai_choices_shape():
    response = AIService._normalize_response(json.dumps({
        "content": [
            {
                "type": "text",
                "text": "پاسخ Claude",
                "citations": [{"url": "https://example.com/claude-source"}],
            },
            {"type": "tool_use", "name": "search"},
        ],
    }))

    assert json.loads(response) == {
        "choices": [{"message": {"content": "پاسخ Claude"}}],
        "sources": ["https://example.com/claude-source"],
    }


def test_leaves_non_gemini_response_unchanged():
    assert AIService._normalize_response('{"choices":[]}') == '{"choices":[]}'


@pytest.mark.asyncio
async def test_user_prompts_use_responses_web_search(monkeypatch):
    class Response:
        status = 200

        async def text(self):
            return '{"output":[]}'

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    class Session:
        def post(self, url, json):
            self.url = url
            self.payload = json
            return Response()

    session = Session()

    async def get_session():
        return session

    monkeypatch.setattr(AIService, "_get_session", staticmethod(get_session))

    _, provider_used = await AIService().run_prompt_with_provider("google/gemini", "latest news")

    assert provider_used == "primary"
    assert session.url.endswith("/v1/responses")
    assert session.payload == {
        "model": "google/gemini",
        "input": "latest news",
        "tools": [{"type": "web_search"}],
        "tool_choice": "auto",
        "include": ["web_search_call.action.sources"],
        "max_output_tokens": 5000,
    }

    response_format = {"type": "json_schema"}
    await AIService().run_prompt("openai/extractor", "extract", response_format)

    assert session.url.endswith("/v1/chat/completions")
    assert session.payload["response_format"] == response_format
    assert "tools" not in session.payload


def test_normalizes_responses_output_to_openai_choices_shape():
    response = AIService._normalize_response(json.dumps({
        "output": [
            {"type": "web_search_call", "status": "completed"},
            {"type": "message", "content": [{"type": "output_text", "text": "fresh answer"}]},
        ],
    }))

    assert json.loads(response) == {
        "choices": [{"message": {"content": "fresh answer"}}],
    }


def test_normalizes_unique_safe_web_sources():
    response = AIService._normalize_response(json.dumps({
        "output": [
            {
                "type": "web_search_call",
                "action": {
                    "sources": [
                        {"type": "url", "url": "https://example.com/report"},
                        {"type": "url", "url": "https://example.com/report"},
                        {"type": "url", "url": "javascript:alert(1)"},
                        {"type": "url", "url": "http://["},
                    ],
                },
            },
            {
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": "fresh answer",
                    "annotations": [{
                        "type": "url_citation",
                        "url": "https://example.org/article",
                    }],
                }],
            },
        ],
    }))

    assert json.loads(response) == {
        "choices": [{"message": {"content": "fresh answer"}}],
        "sources": [
            "https://example.com/report",
            "https://example.org/article",
        ],
    }


@pytest.mark.asyncio
async def test_falls_back_to_avalai_after_primary_retries(monkeypatch):
    class Response:
        request_info = None
        history = ()

        def __init__(self, status, body):
            self.status = status
            self.body = body

        async def text(self):
            return self.body

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

    class Session:
        def __init__(self):
            self.calls = []

        def post(self, url, json, headers=None):
            self.calls.append((url, json, headers))
            if "avalai.ir" in url:
                body = '{"output":[{"type":"message","content":[{"type":"output_text","text":"fallback"}]}]}'
                return Response(200, body)
            return Response(500, "unavailable")

    session = Session()

    async def get_session():
        return session

    async def no_sleep(_):
        return None

    monkeypatch.setattr(AIService, "_get_session", staticmethod(get_session))
    monkeypatch.setattr(ai_service_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(ai_service_module, "settings", SimpleNamespace(
        AI_GATEWAY_BASE_URL="https://primary.example/api",
        AI_GATEWAY_API_KEY="primary-key",
        AVALAI_BASE_URL="https://api.avalai.ir/v1",
        AVALAI_API_KEY="fallback-key",
    ))

    response, provider_used = await AIService().run_prompt_with_provider(
        "anthropic/claude-sonnet-4.6", "latest news",
    )

    assert provider_used == "avalai"
    assert json.loads(response)["choices"][0]["message"]["content"] == "fallback"
    assert len(session.calls) == 4
    fallback_url, fallback_payload, fallback_headers = session.calls[-1]
    assert fallback_url == "https://api.avalai.ir/v1/responses"
    assert fallback_payload["model"] == "claude-sonnet-4-6"
    assert fallback_payload["tools"] == [{"type": "web_search"}]
    assert fallback_headers == {"Authorization": "Bearer fallback-key"}
