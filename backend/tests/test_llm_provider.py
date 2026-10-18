"""Mocked tests for LLM provider response handling."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src import llm_provider
from src.prompt_strategies import apply_strategy


@pytest.fixture(autouse=True)
def isolated_provider(monkeypatch):
    """Keep global provider and progress state isolated between tests."""
    monkeypatch.setattr(llm_provider, "_active_provider", "openai")
    monkeypatch.setattr(llm_provider, "_progress_enabled", False)
    monkeypatch.setattr(llm_provider, "_get_api_key", lambda provider: "test-api-key")


def model_response(content, *, refusal=None, finish_reason="stop", usage=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content, refusal=refusal),
            finish_reason=finish_reason,
        )],
        usage=usage,
    )


def test_complete_returns_content_and_sends_provider_options(monkeypatch):
    messages = [{"role": "user", "content": "Check this address"}]
    response_format = {"type": "json_object"}
    completion = MagicMock(return_value=model_response("Analysis complete"))
    monkeypatch.setattr("litellm.completion", completion)

    result = llm_provider.complete(messages, response_format)

    assert result == "Analysis complete"
    completion.assert_called_once_with(
        model="openai/gpt-4.1-mini",
        messages=apply_strategy(messages, "business_analyser", "zero_shot"),
        api_key="test-api-key",
        max_tokens=8192,
        response_format=response_format,
        temperature=0.1,
    )


def test_complete_with_usage_returns_provider_token_counts(monkeypatch):
    messages = [{"role": "user", "content": "Who are you?"}]
    response = model_response(
        "I am an AI assistant.",
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=6, total_tokens=11),
    )
    completion = MagicMock(return_value=response)
    monkeypatch.setattr("litellm.completion", completion)

    content, usage = llm_provider.complete_with_usage(
        messages, temperature=0, max_tokens=80
    )

    assert content == "I am an AI assistant."
    assert usage == {"input_tokens": 5, "output_tokens": 6, "total_tokens": 11}
    completion.assert_called_once_with(
        model="openai/gpt-4.1-mini",
        messages=apply_strategy(messages, "business_analyser", "zero_shot"),
        api_key="test-api-key",
        max_tokens=80,
        response_format=None,
        temperature=0,
    )


@pytest.mark.parametrize("max_tokens", [0, -1, True, 1.5])
def test_complete_with_usage_rejects_invalid_output_budgets(max_tokens):
    with pytest.raises(ValueError, match="max_tokens must be a positive integer"):
        llm_provider.complete_with_usage([], max_tokens=max_tokens)


def test_complete_with_usage_reports_missing_usage_without_estimation(monkeypatch):
    monkeypatch.setattr(
        "litellm.completion",
        MagicMock(return_value=model_response("I am an AI assistant.")),
    )

    content, usage = llm_provider.complete_with_usage(
        [{"role": "user", "content": "Who are you?"}]
    )

    assert content == "I am an AI assistant."
    assert usage is None


def test_complete_rejects_missing_api_key(monkeypatch):
    monkeypatch.setattr(llm_provider, "_get_api_key", lambda provider: None)
    completion = MagicMock()
    monkeypatch.setattr("litellm.completion", completion)

    with pytest.raises(ValueError, match="Set OPENAI_API_KEY"):
        llm_provider.complete([{"role": "user", "content": "Hello"}])

    completion.assert_not_called()


def test_complete_wraps_provider_failure(monkeypatch):
    monkeypatch.setattr(
        "litellm.completion",
        MagicMock(side_effect=RuntimeError("service unavailable")),
    )

    with pytest.raises(ValueError, match="OpenAI request failed: service unavailable"):
        llm_provider.complete([{"role": "user", "content": "Hello"}])


def test_complete_reports_refusal(monkeypatch):
    monkeypatch.setattr(
        "litellm.completion",
        MagicMock(return_value=model_response("", refusal="request refused")),
    )

    with pytest.raises(ValueError, match="model declined this request: request refused"):
        llm_provider.complete([{"role": "user", "content": "Hello"}])


def test_complete_reports_truncated_response(monkeypatch):
    monkeypatch.setattr(
        "litellm.completion",
        MagicMock(return_value=model_response("partial", finish_reason="length")),
    )

    with pytest.raises(ValueError, match="response was incomplete"):
        llm_provider.complete([{"role": "user", "content": "Hello"}])


@pytest.mark.parametrize("content", [None, "", "   "])
def test_complete_rejects_empty_response_content(monkeypatch, content):
    monkeypatch.setattr(
        "litellm.completion",
        MagicMock(return_value=model_response(content)),
    )

    with pytest.raises(ValueError, match="returned an empty response"):
        llm_provider.complete([{"role": "user", "content": "Hello"}])


@pytest.mark.parametrize(
    "content",
    [
        [{"type": "text", "text": "first "}, {"type": "text", "text": "second"}],
        [SimpleNamespace(text="first "), SimpleNamespace(text="second")],
    ],
)
def test_complete_joins_text_content_blocks(monkeypatch, content):
    monkeypatch.setattr(
        "litellm.completion",
        MagicMock(return_value=model_response(content)),
    )

    assert llm_provider.complete([]) == "first second"
