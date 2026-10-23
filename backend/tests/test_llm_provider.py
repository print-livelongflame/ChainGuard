"""Mocked tests for LLM provider response handling."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src import llm_provider
from src.llm_config import AgentTokenLimits, LLMConfig, ProviderModels
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
        messages, temperature=0
    )

    assert content == "I am an AI assistant."
    assert usage == {"input_tokens": 5, "output_tokens": 6, "total_tokens": 11}
    completion.assert_called_once_with(
        model="openai/gpt-4.1-mini",
        messages=apply_strategy(messages, "business_analyser", "zero_shot"),
        api_key="test-api-key",
        response_format=None,
        temperature=0,
    )


def test_saved_provider_model_is_used_for_cloud_completion(monkeypatch):
    completion = MagicMock(return_value=model_response("Using configured model"))
    monkeypatch.setattr("litellm.completion", completion)
    settings = LLMConfig(models=ProviderModels(openai="openai/gpt-5"))

    with llm_provider.use_llm_settings(settings):
        result = llm_provider.complete([{"role": "user", "content": "Hello"}])

    assert result == "Using configured model"
    assert completion.call_args.kwargs["model"] == "openai/gpt-5"


def test_token_usage_tracker_sums_provider_usage_between_replies(monkeypatch):
    completion = MagicMock(side_effect=[
        model_response(
            "First answer",
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=6, total_tokens=11),
        ),
        model_response(
            "Second answer",
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=8, total_tokens=15),
        ),
    ])
    monkeypatch.setattr("litellm.completion", completion)

    with llm_provider.track_token_usage() as tracker:
        llm_provider.complete([{"role": "user", "content": "First"}])
        first_reply = tracker.checkpoint()
        llm_provider.complete([{"role": "user", "content": "Second"}])

        assert tracker.since(0) == {
            "input_tokens": 12,
            "output_tokens": 14,
            "total_tokens": 26,
        }
        assert tracker.since(first_reply) == {
            "input_tokens": 7,
            "output_tokens": 8,
            "total_tokens": 15,
        }


def test_token_usage_tracker_does_not_estimate_missing_provider_usage(monkeypatch):
    monkeypatch.setattr(
        "litellm.completion",
        MagicMock(return_value=model_response("Answer")),
    )

    with llm_provider.track_token_usage() as tracker:
        llm_provider.complete([{"role": "user", "content": "Question"}])

        assert tracker.since(0) is None


@pytest.mark.parametrize(
    "agent",
    ["business_analyser", "scam_checker", "forensic_investigator"],
)
def test_configured_output_token_limit_is_sent_to_cloud_provider(monkeypatch, agent):
    completion = MagicMock(return_value=model_response("Limited response"))
    monkeypatch.setattr("litellm.completion", completion)
    settings = LLMConfig(token_limits=AgentTokenLimits(**{agent: 321}))

    with llm_provider.use_llm_settings(settings):
        llm_provider.complete([{"role": "user", "content": "Hello"}], agent=agent)

    assert completion.call_args.kwargs["max_tokens"] == 321


def test_configured_output_token_limit_is_sent_to_local_provider(monkeypatch):
    from src.llm_config import Assignments, LocalConfig

    settings = LLMConfig(
        assignments=Assignments(business_analyser="local"),
        token_limits=AgentTokenLimits(business_analyser=654),
        local=LocalConfig(enabled=True),
        local_verified=True,
    )
    request = MagicMock(return_value={"choices": [{"finish_reason": "stop", "message": {"content": "Limited response"}}]})
    monkeypatch.setattr(llm_provider, "local_request", request)

    with llm_provider.use_llm_settings(settings):
        llm_provider.complete([{"role": "user", "content": "Hello"}])

    assert request.call_args.args[2]["max_tokens"] == 654


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
