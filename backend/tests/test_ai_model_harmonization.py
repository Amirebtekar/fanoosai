from app.services.ai_model_service import AIModelService
from app.services.ai_service import avalai_model_key


def test_avalai_model_key_normalizes_provider_prefix_and_claude_version():
    assert avalai_model_key("openai/gpt-5.1-chat") == "gpt-5.1-chat"
    assert avalai_model_key("anthropic/claude-sonnet-4.6") == "claude-sonnet-4-6"
    assert avalai_model_key("google/gemini-3.1-pro-preview") == "gemini-3.1-pro-preview"
    assert avalai_model_key("google/gemma-3-12b-it") == "cf.gemma-3-12b-it"
    assert avalai_model_key("meta-llama/llama-3.2-3b-instruct") == "cf.llama-3.2-3b-instruct"
    assert avalai_model_key("nvidia/nemotron-nano-12b-v2-vl") == "nvidia_nim.nemotron-nano-12b-v2-vl"
    assert avalai_model_key("qwen/qwen-3.7-plus") == "qwen3.7-plus"
    assert avalai_model_key("x-ai/grok-4-fast") == "grok-4-fast-reasoning"
    assert avalai_model_key("x-ai/grok-4.1-fast") == "grok-4-1-fast-reasoning"
    assert avalai_model_key("x-ai/grok-4.20") == "grok-4.20-reasoning"


def test_harmonization_keeps_only_models_available_in_both_gateways():
    parspack = {"data": [
        {"id": "openai/gpt-5.1-chat", "owned_by": "OpenAI"},
        {"id": "anthropic/claude-sonnet-4.6", "owned_by": "Anthropic"},
        {"id": "google/gemma-3-12b-it", "owned_by": "Google"},
        {"id": "x-ai/grok-4-fast", "owned_by": "xAI"},
        {"id": "x-ai/grok-4", "owned_by": "xAI"},
        {"id": "x-ai/grok-3", "owned_by": "xAI"},
        {"id": "x-ai/grok-4.20-multi-agent", "owned_by": "xAI"},
        {"id": "x-ai/primary-only", "owned_by": "xAI"},
    ]}
    avalai = {"data": [
        {"id": "gpt-5.1-chat", "owned_by": "openai"},
        {"id": "claude-sonnet-4-6", "owned_by": "anthropic"},
        {"id": "cf.gemma-3-12b-it", "owned_by": "google"},
        {"id": "grok-4-fast-reasoning", "owned_by": "xai"},
        {"id": "grok-4", "owned_by": "xai"},
        {"id": "grok-3", "owned_by": "xai"},
        {"id": "grok-4.20-multi-agent", "owned_by": "xai"},
        {"id": "fallback-only", "owned_by": "other"},
    ]}

    rows = AIModelService._common_gateway_models(parspack, avalai)

    assert [row["model_key"] for row in rows] == [
        "openai/gpt-5.1-chat",
        "anthropic/claude-sonnet-4.6",
        "google/gemma-3-12b-it",
        "x-ai/grok-4-fast",
        "x-ai/grok-4",
        "x-ai/grok-3",
        "x-ai/grok-4.20-multi-agent",
    ]


def test_harmonization_excludes_primary_models_missing_from_fallback():
    rows = AIModelService._common_gateway_models(
        {"data": [{"id": "google/gemini-3.1-pro-preview", "owned_by": "Google"}]},
        {"data": []},
    )

    assert rows == []


def test_harmonization_excludes_unmatched_primary_model():
    rows = AIModelService._common_gateway_models(
        {"data": [{"id": "x-ai/grok-4", "owned_by": "xAI"}]},
        {"data": [{"id": "grok-4-fast-reasoning", "owned_by": "xai"}]},
    )

    assert rows == []


def test_harmonization_uses_canonical_model_key_for_display_name():
    rows = AIModelService._normalize_gateway_models({
        "data": [{"id": "openai/gpt-5-chat", "name": "GPT-5", "owned_by": "OpenAI"}],
    })

    assert rows[0]["name"] == "openai/gpt-5-chat"
