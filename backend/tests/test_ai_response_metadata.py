import json
from types import SimpleNamespace

import pytest

import app.services.ai_service as ai_service_module
from app.services.ai_service import AIService, extract_response_metadata
from app.services.errors import AIProviderError

METADATA_KEYS = {
    "prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "cached_tokens",
    "cost_irt", "cost_usd", "web_search_count", "web_search_queries", "web_search_actions", "citations",
}

SAMPLE_WITH_COST = {
    "id": "resp_0a1",
    "object": "response",
    "status": "completed",
    "model": "gpt-5.4",
    "output": [
        {"id": "rs_1", "type": "reasoning", "encrypted_content": "gAAAAABp-encrypted", "summary": []},
        {
            "id": "ws_1",
            "type": "web_search_call",
            "status": "completed",
            "action": {
                "type": "search",
                "queries": ["بهترین هاست ایران", "best iranian hosting 2026"],
                "query": "بهترین هاست ایران",
                "sources": None,
            },
        },
        {"id": "rs_2", "type": "reasoning", "encrypted_content": "gAAAAABp-more", "summary": []},
        {
            "id": "ws_2",
            "type": "web_search_call",
            "status": "completed",
            "action": {"type": "open_page", "url": "https://openai.com/news/"},
        },
        {
            "id": "ws_3",
            "type": "web_search_call",
            "status": "completed",
            "action": {"type": "find_in_page", "pattern": "نماد", "url": "https://sibchob.ir/"},
        },
        {
            "id": "ws_4",
            "type": "web_search_call",
            "status": "completed",
            "action": {
                "type": "search",
                "queries": ["best iranian hosting 2026", "پارس پک"],
                "query": "best iranian hosting 2026",
                "sources": [
                    {"type": "url", "url": "https://parspack.com/"},
                    {"type": "url", "url": "javascript:alert(1)"},
                ],
            },
        },
        {
            "id": "msg_1",
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [{
                "type": "output_text",
                "text": "پاسخ نهایی",
                "annotations": [
                    {"type": "url_citation", "url": "https://parspack.com/", "title": "پارس پک", "start_index": 0, "end_index": 4},
                    {"type": "url_citation", "url": "https://parspack.com/", "title": "duplicate", "start_index": 5, "end_index": 9},
                    {"type": "url_citation", "url": "https://sibchob.ir/", "title": "سیب چوب", "start_index": 10, "end_index": 14},
                    {"type": "url_citation", "url": "ftp://files.example/", "title": "ftp"},
                ],
            }],
        },
    ],
    "usage": {
        "input_tokens": 41234,
        "input_tokens_details": {"cached_tokens": 1024},
        "output_tokens": 2311,
        "output_tokens_details": {"reasoning_tokens": 1650},
        "total_tokens": 43545,
    },
    "tool_usage": {"web_search": {"num_requests": 10}},
    "estimated_cost": {"unit": "0.3589430500", "irt": 97399.2, "exchange_rate": 271350},
}

SAMPLE_WITHOUT_COST = {
    "id": "resp_0b2",
    "object": "response",
    "status": "completed",
    "output": [
        {
            "type": "web_search_call",
            "status": "completed",
            "action": {"type": "find_in_page", "pattern": "قیمت", "url": "https://example.ir/prices"},
        },
        {
            "type": "message",
            "content": [{"type": "output_text", "text": "جواب", "annotations": []}],
        },
    ],
    "usage": {"input_tokens": 900, "output_tokens": 120, "total_tokens": 1020},
}


def test_extracts_full_responses_metadata_with_cost():
    metadata = extract_response_metadata(json.dumps(SAMPLE_WITH_COST, ensure_ascii=False))

    assert set(metadata) == METADATA_KEYS
    assert metadata["prompt_tokens"] == 41234
    assert metadata["completion_tokens"] == 2311
    assert metadata["total_tokens"] == 43545
    assert metadata["reasoning_tokens"] == 1650
    assert metadata["cached_tokens"] == 1024
    assert metadata["cost_irt"] == 97399.2
    assert metadata["cost_usd"] == pytest.approx(0.35894305)
    assert isinstance(metadata["cost_usd"], float)
    assert metadata["web_search_count"] == 10
    assert metadata["web_search_queries"] == ["بهترین هاست ایران", "best iranian hosting 2026", "پارس پک"]
    assert metadata["web_search_actions"] == [
        {"type": "search", "queries": ["بهترین هاست ایران", "best iranian hosting 2026"]},
        {"type": "open_page", "url": "https://openai.com/news/"},
        {"type": "find_in_page", "url": "https://sibchob.ir/", "pattern": "نماد"},
        {"type": "search", "queries": ["best iranian hosting 2026", "پارس پک"], "sources": ["https://parspack.com/"]},
    ]
    assert metadata["citations"] == [
        {"url": "https://parspack.com/", "title": "پارس پک"},
        {"url": "https://sibchob.ir/", "title": "سیب چوب"},
    ]
    json.dumps(metadata)


def test_extracts_usage_without_cost_and_counts_no_searches_for_find_in_page_only():
    metadata = extract_response_metadata(json.dumps(SAMPLE_WITHOUT_COST, ensure_ascii=False))

    assert metadata["prompt_tokens"] == 900
    assert metadata["completion_tokens"] == 120
    assert metadata["total_tokens"] == 1020
    assert metadata["reasoning_tokens"] is None
    assert metadata["cached_tokens"] is None
    assert metadata["cost_irt"] is None
    assert metadata["cost_usd"] is None
    assert metadata["web_search_count"] == 0
    assert metadata["web_search_queries"] == []
    assert metadata["web_search_actions"] == [{"type": "find_in_page", "url": "https://example.ir/prices", "pattern": "قیمت"}]
    assert metadata["citations"] == []


def test_counts_search_items_when_tool_usage_is_missing():
    body = {"output": [
        {"type": "web_search_call", "action": {"type": "search", "query": "a", "sources": None}},
        {"type": "web_search_call", "action": {"type": "search", "queries": ["b", "a"]}},
        {"type": "web_search_call", "action": {"type": "open_page", "url": "https://a.example/"}},
        {"type": "web_search_call", "status": "completed"},
    ]}
    metadata = extract_response_metadata(json.dumps(body))
    assert metadata["web_search_count"] == 2
    assert metadata["web_search_queries"] == ["a", "b"]
    assert metadata["web_search_actions"][0] == {"type": "search", "query": "a"}


def test_chat_completions_usage_style_and_annotations():
    body = {
        "choices": [{"message": {
            "content": "answer",
            "annotations": [{"type": "url_citation", "url_citation": {"url": "https://news.example/a", "title": "A"}}],
        }}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "completion_tokens_details": {"reasoning_tokens": 3}},
        "estimated_cost": {"irt": "1200.5", "unit": 0.004},
    }
    metadata = extract_response_metadata(json.dumps(body))
    assert (metadata["prompt_tokens"], metadata["completion_tokens"], metadata["total_tokens"]) == (10, 5, 15)
    assert metadata["reasoning_tokens"] == 3
    assert metadata["cost_irt"] == 1200.5
    assert metadata["cost_usd"] == 0.004
    assert metadata["citations"] == [{"url": "https://news.example/a", "title": "A"}]
    assert metadata["web_search_count"] is None


def test_chat_completions_without_usage_returns_empty_values():
    metadata = extract_response_metadata('{"choices":[{"message":{"content":"ok"}}]}')
    assert metadata["total_tokens"] is None
    assert metadata["citations"] == []
    assert metadata["web_search_actions"] == []


def test_router_data_wrapper_with_trailing_sse_frame():
    body = (
        '{"data":{"choices":[{"message":{"content":"پاسخ روتر"}}],'
        '"usage":{"prompt_tokens":7,"completion_tokens":3,"total_tokens":10}},'
        '"estimated_cost":{"irt":55,"unit":"0.0002"},"success":true}\ndata: [DONE]'
    )
    metadata = extract_response_metadata(body)
    assert metadata["total_tokens"] == 10
    assert metadata["cost_irt"] == 55.0
    assert metadata["cost_usd"] == 0.0002


def test_router_data_wrapper_around_responses_output():
    body = {"data": dict(SAMPLE_WITH_COST), "success": True}
    metadata = extract_response_metadata(json.dumps(body))
    assert metadata["cost_irt"] == 97399.2
    assert metadata["web_search_count"] == 10
    assert len(metadata["citations"]) == 2


def test_total_tokens_derived_when_missing():
    metadata = extract_response_metadata('{"output":[],"usage":{"input_tokens":"12","output_tokens":8}}')
    assert metadata["prompt_tokens"] == 12
    assert metadata["total_tokens"] == 20


def test_anthropic_content_blocks():
    body = {
        "content": [
            {"type": "server_tool_use", "name": "web_search", "input": {"query": "claude shannon birth date"}},
            {"type": "web_search_tool_result", "content": [
                {"type": "web_search_result", "url": "https://en.wikipedia.org/wiki/Claude_Shannon", "title": "Claude Shannon - Wikipedia"},
            ]},
            {"type": "web_search_tool_result", "content": {"type": "web_search_tool_result_error", "error_code": "max_uses_exceeded"}},
            {"type": "text", "text": "born 1916", "citations": [
                {"type": "web_search_result_location", "url": "https://en.wikipedia.org/wiki/Claude_Shannon", "title": "Claude Shannon - Wikipedia"},
                {"url": "https://other.example/x"},
            ]},
        ],
        "usage": {"input_tokens": 6039, "output_tokens": 931, "cache_read_input_tokens": 100, "server_tool_use": {"web_search_requests": 1}},
    }
    metadata = extract_response_metadata(json.dumps(body))
    assert metadata["web_search_queries"] == ["claude shannon birth date"]
    assert metadata["web_search_actions"] == [{"type": "search", "query": "claude shannon birth date"}]
    assert metadata["web_search_count"] == 1
    assert metadata["cached_tokens"] == 100
    assert metadata["total_tokens"] == 6970
    assert metadata["citations"] == [
        {"url": "https://en.wikipedia.org/wiki/Claude_Shannon", "title": "Claude Shannon - Wikipedia"},
        {"url": "https://other.example/x", "title": None},
    ]


def test_gemini_grounding_metadata():
    body = {
        "candidates": [{
            "content": {"parts": [{"text": "answer"}]},
            "groundingMetadata": {
                "webSearchQueries": ["q one", "q two", "q one"],
                "groundingChunks": [
                    {"web": {"uri": "https://vertexaisearch.cloud.google.com/redirect/abc", "title": "example.com"}},
                    {"web": {"uri": "not a url"}},
                ],
            },
        }],
        "usageMetadata": {"promptTokenCount": 30, "candidatesTokenCount": 20, "totalTokenCount": 55, "thoughtsTokenCount": 5},
    }
    metadata = extract_response_metadata(json.dumps(body))
    assert metadata["web_search_queries"] == ["q one", "q two"]
    assert metadata["web_search_count"] == 3
    assert metadata["citations"] == [{"url": "https://vertexaisearch.cloud.google.com/redirect/abc", "title": "example.com"}]
    assert (metadata["prompt_tokens"], metadata["completion_tokens"], metadata["total_tokens"], metadata["reasoning_tokens"]) == (30, 20, 55, 5)


@pytest.mark.parametrize("body", [
    None, 123, b"", "", "not json", "{", "[1,2,3]", '{"output": "oops"}', '{"output": [null, 1, "x"]}',
    '{"usage": "bad", "estimated_cost": [1], "tool_usage": {"web_search": 5}}',
    '{"usage": {"input_tokens": "abc", "output_tokens": true, "total_tokens": NaN}}',
    '{"estimated_cost": {"irt": "Infinity", "unit": {}}}',
    '{"output": [{"type": "web_search_call", "action": {"type": "search", "queries": "x", "sources": "y"}}]}',
    '{"output": [{"type": "message", "content": [{"annotations": [null, {"type": "url_citation", "url": 5}]}]}]}',
    '{"choices": [null]}', '{"content": [null, {"type": "web_search_tool_result", "content": [null]}]}',
    '{"candidates": [null, {"groundingMetadata": {"groundingChunks": [null, {"web": null}]}}]}',
])
def test_malformed_input_never_raises(body):
    metadata = extract_response_metadata(body)
    assert set(metadata) == METADATA_KEYS
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "cached_tokens", "cost_irt", "cost_usd"):
        assert metadata[key] is None or isinstance(metadata[key], (int, float))
    json.dumps(metadata, allow_nan=False)


def test_bytes_body_and_sse_completed_event():
    completed = {"type": "response.completed", "response": SAMPLE_WITHOUT_COST}
    sse = "event: response.completed\ndata: " + json.dumps(completed) + "\n\ndata: [DONE]\n"
    metadata = extract_response_metadata(sse.encode("utf-8"))
    assert metadata["total_tokens"] == 1020
    assert metadata["web_search_actions"][0]["type"] == "find_in_page"


def test_non_http_urls_are_filtered_everywhere():
    body = {"output": [
        {"type": "web_search_call", "action": {"type": "open_page", "url": "javascript:alert(1)"}},
        {"type": "web_search_call", "action": {"type": "find_in_page", "url": "file:///etc/passwd", "pattern": "root"}},
        {"type": "message", "content": [{"type": "output_text", "text": "x", "annotations": [
            {"type": "url_citation", "url": "data:text/html,hi", "title": "bad"},
            {"type": "url_citation", "url": "http://[", "title": "bad"},
            {"type": "url_citation", "url": "https:///no-host", "title": "bad"},
        ]}]},
    ]}
    metadata = extract_response_metadata(json.dumps(body))
    assert metadata["web_search_actions"] == [{"type": "open_page"}, {"type": "find_in_page", "pattern": "root"}]
    assert metadata["citations"] == []


def test_duplicate_citations_keep_first_position_and_fill_missing_title():
    body = {"output": [{"type": "message", "content": [{"type": "output_text", "text": "x", "annotations": [
        {"type": "url_citation", "url": "https://a.example/"},
        {"type": "url_citation", "url": "https://b.example/", "title": "B"},
        {"type": "url_citation", "url": "https://a.example/", "title": "A"},
        {"type": "url_citation", "url": "https://b.example/", "title": "B2"},
    ]}]}]}
    metadata = extract_response_metadata(json.dumps(body))
    assert metadata["citations"] == [{"url": "https://a.example/", "title": "A"}, {"url": "https://b.example/", "title": "B"}]


def _settings(**overrides):
    values = {
        "AI_GATEWAY_ENABLED": True,
        "AI_GATEWAY_BASE_URL": "https://primary.example/api",
        "AI_GATEWAY_API_KEY": "primary-key",
        "AVALAI_BASE_URL": "https://api.avalai.ir/v1",
        "AVALAI_API_KEY": "fallback-key",
        "AVALAI_MODEL": "",
        "AI_TOTAL_DEADLINE_SECONDS": 60,
        "RUN_CLAIM_LEASE_SECONDS": 600,
        "AI_MAX_RETRIES": 0,
        "AI_RETRY_BASE_DELAY": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _Response:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    async def text(self):
        return self.body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, json, headers=None, **_):
        self.calls.append((url, json))
        status, body = self.responses.pop(0)
        return _Response(status, body)


def _install(monkeypatch, session, **overrides):
    async def get_session():
        return session

    monkeypatch.setattr(AIService, "_get_session", staticmethod(get_session))
    monkeypatch.setattr(ai_service_module, "settings", _settings(**overrides))


@pytest.mark.asyncio
async def test_run_prompt_sets_last_usage_from_raw_body(monkeypatch):
    session = _Session([(200, json.dumps(SAMPLE_WITH_COST, ensure_ascii=False))])
    _install(monkeypatch, session)
    service = AIService()

    response, provider = await service.run_prompt_with_provider("openai/gpt-5.4", "سوال")

    assert provider == "primary"
    assert json.loads(response) == {
        "choices": [{"message": {"content": "پاسخ نهایی"}}],
        "sources": ["https://parspack.com/", "https://sibchob.ir/"],
    }
    assert service.last_usage["cost_irt"] == 97399.2
    assert service.last_usage["cost_usd"] == pytest.approx(0.35894305)
    assert service.last_usage["total_tokens"] == 43545
    assert service.last_usage["prompt_tokens"] == 41234
    assert service.last_usage["web_search_count"] == 10
    assert service.last_usage["web_search_queries"][0] == "بهترین هاست ایران"
    assert session.calls[0][1]["tools"] == [{"type": "web_search"}]


@pytest.mark.asyncio
async def test_last_usage_is_reset_per_call_and_per_instance(monkeypatch):
    session = _Session([
        (200, json.dumps(SAMPLE_WITH_COST, ensure_ascii=False)),
        (200, '{"output":[]}'),
    ])
    _install(monkeypatch, session, AVALAI_API_KEY="")
    service = AIService()
    await service.run_prompt_with_provider("openai/gpt-5.4", "q1")
    assert service.last_usage["cost_irt"] == 97399.2
    assert AIService().last_usage == {}
    assert "last_usage" not in AIService.__dict__ or not isinstance(AIService.__dict__["last_usage"], dict)

    with pytest.raises(ValueError):
        await service.run_prompt_with_provider("openai/gpt-5.4", "q2")
    assert service.last_usage == {}


@pytest.mark.asyncio
async def test_fallback_usage_comes_from_fallback_raw_body(monkeypatch):
    fallback_body = json.dumps({
        "choices": [{"message": {"content": "fallback"}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15},
        "estimated_cost": {"irt": 321},
    })
    session = _Session([(500, "unavailable"), (200, fallback_body)])
    _install(monkeypatch, session)
    service = AIService()

    _, provider = await service.run_prompt_with_provider("openai/gpt-5.4", "q")

    assert provider == "9router"
    assert service.last_usage["total_tokens"] == 15
    assert service.last_usage["cost_irt"] == 321.0
    assert service.last_usage["web_search_queries"] == []


@pytest.mark.asyncio
async def test_extraction_call_overwrites_usage_only_after_run_is_captured(monkeypatch):
    extraction_body = json.dumps({
        "choices": [{"message": {"content": '{"brands": []}'}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })
    session = _Session([(200, json.dumps(SAMPLE_WITH_COST, ensure_ascii=False)), (200, extraction_body)])
    _install(monkeypatch, session)
    service = AIService()

    await service.run_prompt_with_provider("openai/gpt-5.4", "q")
    captured = service.last_usage
    await service.run_prompt("openai/extractor", "extract", {"type": "json_object"})

    assert captured["total_tokens"] == 43545
    assert service.last_usage["total_tokens"] == 2
    assert captured is not service.last_usage


@pytest.mark.asyncio
async def test_error_envelope_still_raises_and_leaves_no_usage(monkeypatch):
    session = _Session([(200, '{"error":{"message":"[401] bad key"}}'), (500, "down")])
    _install(monkeypatch, session)
    service = AIService()
    with pytest.raises(AIProviderError):
        await service.run_prompt_with_provider("openai/gpt-5.4", "q")
    assert service.last_usage == {}
    assert service._response_metadata == {}


def test_legacy_usage_helper_still_reads_chat_style():
    assert AIService._usage('{"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3},"estimated_cost":{"irt":4}}') == {
        "prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3, "cost_irt": 4,
    }
