"""Shared runtime provider selection for ChainGuard's LLM-backed agents."""

import os


_PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "model": "openai/gpt-4.1-mini",
        "environment_keys": ("OPENAI_API_KEY",),
        "config_key": "OPENAI_API_KEY",
    },
    "gemini": {
        "label": "Gemini",
        "model": "gemini/gemini-2.5-flash",
        "environment_keys": ("GEMINI_API_KEY",),
        "config_key": "GEMINI_API_KEY",
    },
    "claude": {
        "label": "Claude",
        "model": "anthropic/claude-sonnet-4-5",
        "environment_keys": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
        "config_key": "CLAUDE_API_KEY",
    },
}
_active_provider = "openai"


def list_providers() -> list[tuple[str, str]]:
    return [(name, details["label"]) for name, details in _PROVIDERS.items()]


def get_provider() -> str:
    return _active_provider


def _get_api_key(provider: str) -> str | None:
    details = _PROVIDERS[provider]
    for environment_key in details["environment_keys"]:
        key = os.environ.get(environment_key)
        if key and key.strip() and key.strip().casefold() != "enter key here":
            return key.strip()

    try:
        from api_keys import api_keys
    except ImportError:
        return None
    key = getattr(api_keys, details["config_key"], None)
    if not isinstance(key, str) or not key.strip():
        return None
    key = key.strip()
    return None if key.casefold() == "enter key here" else key


def set_provider(provider: str) -> str:
    """Select a configured provider for the rest of the current CLI session."""
    global _active_provider

    normalized = provider.strip().casefold()
    if normalized not in _PROVIDERS:
        raise ValueError("Choose openai, gemini, or claude.")

    if not _get_api_key(normalized):
        details = _PROVIDERS[normalized]
        environment_keys = " or ".join(details["environment_keys"])
        raise ValueError(
            f"Set {environment_keys} or {details['config_key']} in "
            "api_keys/api_keys.py before selecting this provider."
        )

    _active_provider = normalized
    return _PROVIDERS[normalized]["label"]


def complete(messages: list[dict[str, str]], response_format: dict | None = None) -> str:
    """Generate text with the selected provider and return its message content."""
    provider = _active_provider
    api_key = _get_api_key(provider)
    if not api_key:
        details = _PROVIDERS[provider]
        environment_keys = " or ".join(details["environment_keys"])
        raise ValueError(
            f"Set {environment_keys} or {details['config_key']} in "
            "api_keys/api_keys.py before making an AI request."
        )

    try:
        from litellm import completion
    except ImportError as error:
        raise ValueError("Install the LLM provider dependency with: pip install -r requirements.txt") from error

    try:
        response = completion(
            model=_PROVIDERS[provider]["model"],
            messages=messages,
            api_key=api_key,
            max_tokens=8192,
            response_format=response_format,
        )
    except Exception as error:
        label = _PROVIDERS[provider]["label"]
        raise ValueError(f"{label} request failed: {error}") from error

    choice = response.choices[0]
    message = choice.message
    refusal = getattr(message, "refusal", None)
    if refusal:
        raise ValueError(f"The {_PROVIDERS[provider]['label']} model declined this request: {refusal}")
    if choice.finish_reason in {"length", "max_tokens"}:
        raise ValueError(f"The {_PROVIDERS[provider]['label']} response was incomplete (token limit).")

    content = message.content
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") if isinstance(item, dict) else getattr(item, "text", "")
            for item in content
        )
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"The {_PROVIDERS[provider]['label']} returned an empty response.")
    return content