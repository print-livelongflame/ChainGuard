"""Persist web agent assignments and a verified local model connection."""
import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

Provider = Literal["openai", "claude", "gemini", "local"]
CONFIG_PATH = Path(os.environ.get("CHAINGUARD_LLM_CONFIG_PATH", Path(__file__).resolve().parents[1] / "llm_config.json"))
CONFIG_LOCK = RLock()


class Assignments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_analyser: Provider = "openai"
    scam_checker: Provider = "openai"
    forensic_investigator: Provider = "openai"


class AgentTuning(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt_strategy: Literal["zero_shot", "chain_of_thought", "few_shot"] = "zero_shot"
    temperature: float = Field(default=0.1, ge=0, le=1, allow_inf_nan=False)


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_analyser: AgentTuning = Field(default_factory=AgentTuning)
    scam_checker: AgentTuning = Field(default_factory=lambda: AgentTuning(prompt_strategy="chain_of_thought", temperature=0.2))
    forensic_investigator: AgentTuning = Field(default_factory=AgentTuning)


class LocalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    name: str = Field(default="My local LLM", min_length=1, max_length=100, pattern=r"\S")
    base_url: str = "http://chainguard-local-llm:9010/v1"
    model: str = Field(default="llama3.2:3b", min_length=1, max_length=200, pattern=r"\S")
    api_key: str = Field(default="", max_length=1000)
    timeout_seconds: int = Field(default=300, ge=10, le=1800)

    @field_validator("base_url")
    @classmethod
    def valid_url(cls, value):
        value = value.strip().rstrip("/")
        parsed = urlsplit(value)
        try:
            parsed.port
        except ValueError:
            raise ValueError("The endpoint port is invalid.")
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Use an http:// or https:// URL without embedded credentials or query parameters.")
        if not parsed.path.endswith("/v1"):
            raise ValueError("Use the base URL ending in /v1, not /chat/completions or /docs.")
        return value


class LocalUpdate(LocalConfig):
    # null preserves a saved key; an empty string explicitly removes it.
    api_key: str | None = Field(default=None, max_length=1000)


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignments: Assignments = Field(default_factory=Assignments)
    agents: AgentSettings = Field(default_factory=AgentSettings)
    local: LocalConfig = Field(default_factory=LocalConfig)
    local_verified: bool = False


def get_llm_settings():
    with CONFIG_LOCK:
        try:
            return LLMConfig.model_validate_json(CONFIG_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            provider = os.environ.get("CHAINGUARD_AI_PROVIDER", "openai").strip().lower()
            return LLMConfig(assignments=Assignments(**{role: provider for role in Assignments.model_fields}))
        except (OSError, ValueError) as error:
            raise ValueError("Cannot read LLM settings.") from error


def settings_exist():
    return CONFIG_PATH.exists()


def save_llm_settings(config):
    with CONFIG_LOCK:
        temporary = None
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CONFIG_PATH.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(config.model_dump_json(indent=2))
            temporary.replace(CONFIG_PATH)
        except OSError as error:
            raise ValueError("Cannot save LLM settings.") from error
        finally:
            if temporary and temporary.exists():
                temporary.unlink()


def merge_local(update, saved):
    values = update.model_dump()
    values["api_key"] = saved.api_key if update.api_key is None else update.api_key
    return LocalConfig(**values)


def local_request(config, path, body=None, *, timeout=None):
    headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
    try:
        with httpx.Client(timeout=timeout or config.timeout_seconds, follow_redirects=False, trust_env=False) as client:
            response = client.request("POST" if body is not None else "GET", f"{config.base_url}/{path}", json=body, headers=headers)
            if response.status_code in (401, 403):
                raise ValueError("Local LLM rejected the API key.")
            if not response.is_success:
                raise ValueError(f"Local LLM returned HTTP {response.status_code}. Check the model name, endpoint and server logs.")
            return response.json()
    except httpx.TimeoutException as error:
        raise ValueError("Local LLM timed out. Try a smaller model or increase the timeout.") from error
    except httpx.RequestError as error:
        raise ValueError("Cannot reach the local LLM. Check that it is running and connected to ChainGuard's Docker network.") from error
    except json.JSONDecodeError as error:
        raise ValueError("Local LLM returned an invalid response.") from error


def local_content(data):
    try:
        choice = data["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("Local LLM did not finish its answer. The output may have reached its token limit.")
        content = choice["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Local LLM returned an empty answer.")
        return content
    except (KeyError, IndexError, TypeError, AttributeError) as error:
        raise ValueError("Local LLM returned an invalid chat response.") from error


def check_local(config):
    data = local_request(config, "models", timeout=5)
    try:
        if config.model not in [item["id"] for item in data["data"]]:
            raise ValueError("The model name is not in the server's installed model list. Use the exact downloaded name.")
    except (KeyError, TypeError) as error:
        raise ValueError("Local LLM returned an invalid model list.") from error


def test_local(config):
    check_local(config)
    schema = {"type": "object", "properties": {"connected": {"type": "boolean", "enum": [True]}}, "required": ["connected"], "additionalProperties": False}
    data = local_request(config, "chat/completions", {
        "model": config.model, "messages": [{"role": "system", "content": 'Return only {"connected": true} as JSON.'}, {"role": "user", "content": "Test connection."}],
        "stream": False, "temperature": 0, "max_tokens": 100,
        "response_format": {"type": "json_schema", "json_schema": {"name": "connection_test", "strict": True, "schema": schema}},
    })
    try:
        result = json.loads(local_content(data))
        if not isinstance(result, dict) or result != {"connected": True} or result["connected"] is not True:
            raise ValueError("The local model failed the structured JSON test. Try a different model.")
    except json.JSONDecodeError as error:
        raise ValueError("The local model did not return valid JSON. Try a different model.") from error


def public_settings(config, *, probe=True):
    connected, error = False, None
    if config.local.enabled and config.local_verified:
        try:
            if probe:
                check_local(config.local)
            connected = True
        except ValueError as failure:
            error = str(failure)
    local = config.local.model_dump(exclude={"api_key"})
    local.update(api_key_configured=bool(config.local.api_key), connected=connected, connection_error=error)
    return {"assignments": config.assignments.model_dump(), "agents": config.agents.model_dump(), "local": local}
