"""Mocked tests for LLM provider response handling."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src import llm_provider


@pytest.fixture(autouse=True)
def isolated_provider(monkeypatch):
    """Keep global provider and progress state isolated between tests."""
    monkeypatch.setattr(llm_provider, "_active_provider", "openai")
    monkeypatch.setattr(llm_provider, "_progress_enabled", False)
    monkeypatch.setattr(llm_provider, "_get_api_key", lambda provider: "test-api-key")


def model_response(content, *, refusal=None, finish_reason="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content, refusal=refusal),
            finish_reason=finish_reason,
        )]
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
        messages=messages,
        api_key="test-api-key",
        max_tokens=8192,
        response_format=response_format,
    )


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
