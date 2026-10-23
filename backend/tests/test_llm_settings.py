"""Local connection, admin permissions, persistence and agent routing."""
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from src.api import create_app
from src.llm_config import (LLMConfig, LocalConfig, Assignments, get_llm_settings,
    ProviderModels, local_request, test_local as probe_local)
from src.llm_provider import complete, use_llm_settings
from test_web_chat import task, envelope


def reply(content):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}


class LLMSettingsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.config_path = Path(directory.name) / "llm.json"
        patches = [patch("src.llm_config.CONFIG_PATH", self.config_path),
                   patch("src.api.set_provider", return_value="OpenAI"),
                   patch("src.llm_settings_api.provider_available", return_value=True),
                   patch.dict(os.environ, {"CHAINGUARD_ADMIN_USERNAME": "admin", "CHAINGUARD_ADMIN_PASSWORD": "pass",
                                           "CHAINGUARD_USER_USERNAME": "user", "CHAINGUARD_USER_PASSWORD": "pass", "CHAINGUARD_AI_PROVIDER": "openai"})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(create_app())
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def login(self, username="admin"):
        self.client.post("/api/auth/login", json={"username": username, "password": "pass"})

    def connect(self, **changes):
        self.login()
        body = {"enabled": True, "name": "My model", "base_url": "http://model:9010/v1", "model": "llama3.2:3b", **changes}
        with patch("src.llm_settings_api.test_local"):
            result = self.client.post("/api/settings/llm/local", json=body)
        self.assertEqual(result.status_code, 200, result.text)
        return result

    def test_admin_only_before_connection_or_writes(self):
        for username, status in [(None, 401), ("user", 403)]:
            if username:
                self.login(username)
            with patch("src.llm_settings_api.test_local") as probe:
                for path, body in [("", None), ("/local/test", {}), ("/local", {}), ("/assignments", {}), ("/models", {}), ("/agents", {}), ("/token-limits", {})]:
                    response = self.client.get("/api/settings/llm" + path) if body is None else self.client.post("/api/settings/llm" + path, json=body)
                    self.assertEqual(response.status_code, status)
                probe.assert_not_called()
            self.assertFalse(self.config_path.exists())

    def test_prompt_settings_defaults_persistence_and_validation(self):
        self.login()
        defaults = self.client.get("/api/settings/llm").json()["agents"]
        self.assertEqual(defaults["scam_checker"], {"prompt_strategy": "chain_of_thought", "temperature": 0.2})
        defaults["business_analyser"] = {"prompt_strategy": "few_shot", "temperature": 0.35}
        response = self.client.post("/api/settings/llm/agents", json=defaults)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(get_llm_settings().agents.business_analyser.temperature, 0.35)
        self.assertEqual(self.client.get("/api/settings/llm").json()["agents"], defaults)
        for invalid in [{"temperature": -0.1}, {"temperature": 1.1}, {"prompt_strategy": "unknown"}, {"extra": True}]:
            body = {**defaults, "business_analyser": {**defaults["business_analyser"], **invalid}}
            self.assertEqual(self.client.post("/api/settings/llm/agents", json=body).status_code, 422)
        # Older saved configs gain defaults without losing provider assignments.
        self.config_path.write_text('{"assignments":{"business_analyser":"claude"}}')
        restored = get_llm_settings()
        self.assertEqual(restored.assignments.business_analyser, "claude")
        self.assertEqual(restored.agents.scam_checker.prompt_strategy, "chain_of_thought")
        self.assertEqual(restored.models, ProviderModels())

    def test_provider_models_are_admin_configurable_validated_and_persisted(self):
        self.login()
        defaults = {
            "openai": "openai/gpt-4.1-mini",
            "claude": "anthropic/claude-sonnet-4-5",
            "gemini": "gemini/gemini-3.6-flash",
        }
        self.assertEqual(self.client.get("/api/settings/llm").json()["models"], defaults)
        models = {
            "openai": "openai/gpt-5",
            "claude": "anthropic/claude-opus-4-1",
            "gemini": "gemini/gemini-2.5-pro",
        }
        response = self.client.post("/api/settings/llm/models", json=models)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["models"], models)
        self.assertEqual(get_llm_settings().models.model_dump(), models)
        self.assertEqual(self.client.get("/api/settings/llm").json()["models"], models)

        for invalid in [
            {"openai": "", "claude": defaults["claude"], "gemini": defaults["gemini"]},
            {"openai": "gpt 5", "claude": defaults["claude"], "gemini": defaults["gemini"]},
            {"openai": "x" * 201, "claude": defaults["claude"], "gemini": defaults["gemini"]},
            {**models, "unexpected": "model"},
        ]:
            self.assertEqual(self.client.post("/api/settings/llm/models", json=invalid).status_code, 422)

    def test_admin_token_limits_default_unlimited_persist_and_validate(self):
        self.login()
        unlimited = {
            "business_analyser": None,
            "scam_checker": None,
            "forensic_investigator": None,
        }
        self.assertEqual(
            self.client.get("/api/settings/llm").json()["token_limits"],
            unlimited,
        )
        limits = {
            "business_analyser": 1200,
            "scam_checker": 1800,
            "forensic_investigator": None,
        }
        response = self.client.post("/api/settings/llm/token-limits", json=limits)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["token_limits"], limits)
        self.assertEqual(get_llm_settings().token_limits.model_dump(), limits)
        self.assertEqual(self.client.get("/api/settings/llm").json()["token_limits"], limits)

        for invalid in [
            {"business_analyser": 0, "scam_checker": None, "forensic_investigator": None},
            {"business_analyser": -1, "scam_checker": None, "forensic_investigator": None},
            {"business_analyser": "unlimited", "scam_checker": None, "forensic_investigator": None},
        ]:
            self.assertEqual(
                self.client.post("/api/settings/llm/token-limits", json=invalid).status_code,
                422,
            )

    def test_prompt_strategy_and_temperature_reach_each_provider_without_mutation(self):
        config = LLMConfig(local=LocalConfig(enabled=True), local_verified=True)
        cloud_response = SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="ok", refusal=None))])
        messages = [{"role": "system", "content": "Role rules."}, {"role": "user", "content": "Question"}]
        with patch("src.llm_provider._get_api_key", return_value="key"), patch("litellm.completion", return_value=cloud_response) as cloud, patch("src.llm_provider.local_request", return_value=reply("ok")) as local, patch("src.llm_provider._progress_enabled", False):
            for provider in ["openai", "claude", "gemini", "local"]:
                for role in type(config.agents).model_fields:
                    setattr(config.assignments, role, provider)
                    for strategy in ["zero_shot", "few_shot", "chain_of_thought"]:
                        getattr(config.agents, role).prompt_strategy = strategy
                        getattr(config.agents, role).temperature = 0.45
                        with use_llm_settings(config):
                            complete(messages, agent=role)
                        body = local.call_args.args[2] if provider == "local" else cloud.call_args.kwargs
                        self.assertEqual(body["temperature"], 0.45)
                        self.assertIn("Prompt strategy: " + strategy, body["messages"][0]["content"])
                        self.assertTrue(body["messages"][0]["content"].startswith("Role rules."))
            self.assertEqual(messages[0]["content"], "Role rules.")

    def test_verification_gate_failed_changes_and_write_only_key(self):
        self.login()
        choices = {"business_analyser": "openai", "scam_checker": "local", "forensic_investigator": "claude"}
        self.assertEqual(self.client.post("/api/settings/llm/assignments", json=choices).status_code, 400)
        response = self.connect(api_key="private-local-key")
        self.assertNotIn("private-local-key", response.text)
        self.assertTrue(response.json()["local"]["api_key_configured"])
        previous = self.config_path.read_text()
        with patch("src.llm_settings_api.test_local", side_effect=ValueError("not reachable")):
            self.assertEqual(self.client.post("/api/settings/llm/local", json={"enabled": True, "model": "wrong"}).status_code, 400)
        self.assertEqual(self.config_path.read_text(), previous)
        self.connect(api_key=None)
        self.assertEqual(get_llm_settings().local.api_key, "private-local-key")
        with patch("src.llm_settings_api.check_local"):
            self.assertEqual(self.client.post("/api/settings/llm/assignments", json=choices).status_code, 200)
        self.assertEqual(self.client.post("/api/settings/llm/local", json={"enabled": False}).status_code, 400)
        with patch("src.llm_config.check_local", side_effect=ValueError("server stopped")):
            status = self.client.get("/api/settings/llm").json()
            self.assertFalse(status["local"]["connected"])
            self.assertNotIn("private-local-key", json.dumps(status))
        self.connect(api_key="")
        self.assertEqual(get_llm_settings().local.api_key, "")

    def test_connection_test_does_not_save_or_enable(self):
        self.login()
        with patch("src.llm_settings_api.test_local"):
            self.assertEqual(self.client.post("/api/settings/llm/local/test", json={}).status_code, 200)
        self.assertFalse(self.config_path.exists())
        self.assertFalse(get_llm_settings().local_verified)

    def test_invalid_url_and_false_connected_output_rejected(self):
        self.login()
        for url in ["ftp://model/v1", "http://user:password@model/v1", "http://model/docs", "http://model:bad/v1"]:
            self.assertEqual(self.client.post("/api/settings/llm/local/test", json={"base_url": url}).status_code, 422)
        models = {"data": [{"id": "llama3.2:3b"}]}
        for content in ["not JSON", '{"connected": false}', '{"connected": 1}', '{"connected": true, "extra": 1}']:
            with patch("src.llm_config.local_request", side_effect=[models, reply(content)]):
                with self.assertRaises(ValueError):
                    probe_local(LocalConfig())
        with patch("src.llm_config.local_request", side_effect=[models, reply('{"connected": true}')]):
            probe_local(LocalConfig())

    def test_uninstalled_model_and_unavailable_assignment_rejected(self):
        self.connect()
        with patch("src.llm_settings_api.check_local", side_effect=ValueError("server offline")):
            response = self.client.post("/api/settings/llm/assignments", json={"business_analyser": "local"})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(get_llm_settings().assignments.business_analyser, "openai")
        with patch("src.llm_config.local_request", return_value={"data": []}):
            with self.assertRaisesRegex(ValueError, "model name"):
                probe_local(LocalConfig())

    def test_local_ba_answers_web_chat_after_restart_without_cloud_key(self):
        self.connect()
        with patch("src.llm_settings_api.check_local"), patch("src.llm_settings_api.provider_available", return_value=False):
            result = self.client.post("/api/settings/llm/assignments", json={"business_analyser": "local"})
            self.assertEqual(result.status_code, 200, result.text)
        with TestClient(create_app()) as restarted, patch("src.llm_provider.local_request", return_value=reply(envelope(task("Answer from my local model")))) as request, patch("agents.ba.load_detector_config", return_value=None):
            chat = restarted.post("/api/chats").json()["id"]
            response = restarted.post(f"/api/chats/{chat}/messages", json={"text": "What is a blockchain?"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["messages"][-1]["text"], "Answer from my local model")
            self.assertEqual(request.call_args.args[2]["response_format"]["json_schema"]["name"], "ba_response")

    def test_role_routing_context_isolation_and_no_cloud_fallback(self):
        config = LLMConfig(assignments=Assignments(business_analyser="openai", scam_checker="local", forensic_investigator="claude"), local=LocalConfig(enabled=True), local_verified=True)
        cloud_response = SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="cloud", refusal=None))])
        with patch("src.llm_provider._get_api_key", return_value="key"), patch("litellm.completion", return_value=cloud_response) as cloud, patch("src.llm_provider.local_request", return_value=reply("local")) as local, patch("src.llm_provider._progress_enabled", False):
            with use_llm_settings(config):
                self.assertEqual(complete([], agent="business_analyser"), "cloud")
                self.assertEqual(complete([], {"type": "json_object"}, agent="scam_checker"), "local")
                self.assertEqual(complete([], agent="forensic_investigator"), "cloud")
            self.assertEqual([call.kwargs["model"] for call in cloud.call_args_list], ["openai/gpt-4.1-mini", "anthropic/claude-sonnet-4-5"])
            self.assertEqual(local.call_args.args[2]["response_format"], {"type": "json_object"})
            self.assertNotIn("max_tokens", local.call_args.args[2])
            def turn(settings):
                with use_llm_settings(settings):
                    return complete([], agent="business_analyser")
            other = config.model_copy(deep=True)
            other.assignments.business_analyser = "local"
            with ThreadPoolExecutor() as pool:
                self.assertEqual(list(pool.map(turn, [config, other])), ["cloud", "local"])
            with use_llm_settings(other), patch("src.llm_provider.local_request", side_effect=ValueError("offline")):
                before = cloud.call_count
                with self.assertRaisesRegex(ValueError, "offline"):
                    complete([])
                self.assertEqual(cloud.call_count, before)

    def test_forensic_lookup_also_uses_fi_assignment(self):
        from agents.fi import analyze_lookup
        config = LLMConfig(assignments=Assignments(forensic_investigator="local"), local=LocalConfig(enabled=True), local_verified=True)
        with use_llm_settings(config), patch("src.llm_provider.local_request", return_value=reply('{"explanation":"Lookup evidence summary","filename":"lookup.json"}')) as request:
            self.assertEqual(analyze_lookup([], "Explain this address").explanation, "Lookup evidence summary")
            self.assertEqual(request.call_args.args[2]["response_format"]["json_schema"]["name"], "lookup_analysis")

    def test_http_translation_auth_and_failures(self):
        real_client = httpx.Client
        config = LocalConfig(base_url="http://model:9010/v1", api_key="secret")
        def handler(request):
            self.assertEqual(str(request.url), "http://model:9010/v1/chat/completions")
            self.assertEqual(request.headers["authorization"], "Bearer secret")
            self.assertEqual(json.loads(request.content)["model"], "llama3.2:3b")
            return httpx.Response(200, json=reply("hello"))
        def factory(**kwargs):
            return real_client(transport=httpx.MockTransport(handler), **kwargs)
        with patch("src.llm_config.httpx.Client", side_effect=factory):
            self.assertEqual(local_request(config, "chat/completions", {"model": config.model}), reply("hello"))
        for failure, expected in [(httpx.ConnectError("offline"), "Cannot reach"), (httpx.ReadTimeout("slow"), "timed out")]:
            with patch("src.llm_config.httpx.Client") as client:
                client.return_value.__enter__.return_value.request.side_effect = failure
                with self.assertRaisesRegex(ValueError, expected):
                    local_request(config, "models")
