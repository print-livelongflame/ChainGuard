"""Run from backend/: python -m unittest discover -s tests -v."""
import io
import json
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.api import InputAttachment, create_app
from src.chat_service import MAX_ATTACHMENT_BYTES
from src.main import handle_ba_request


def task(message="A blockchain answer", **changes):
    data = dict(
        in_scope=True, request_type="general_question", raw_input=None,
        chain=None, selected_detector=None, detector_configured=False,
        required_input_type=None, needs_resolution=False, resolution_plan=[],
        requested_fields=[], message=message,
    )
    data.update(changes)
    return data


def envelope(*tasks):
    return json.dumps({"tasks": list(tasks)})


class WebChatTests(unittest.TestCase):
    def setUp(self):
        self.provider = patch("src.api.set_provider", return_value="OpenAI")
        self.provider.start()
        self.addCleanup(self.provider.stop)
        self.detector = patch("agents.ba.load_detector_config", return_value=None)
        self.detector.start()
        self.addCleanup(self.detector.stop)
        self.model = patch("agents.ba.complete", return_value=envelope(task()))
        self.complete = self.model.start()
        self.addCleanup(self.model.stop)
        self.app = create_app()
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def create(self):
        response = self.client.post("/api/chats")
        self.assertEqual(response.status_code, 201)
        return response.json()["id"]

    def send(self, chat, text="What is a blockchain?"):
        return self.client.post(f"/api/chats/{chat}/messages", json={"text": text})

    def test_health_route(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})

    def test_api_key_settings_write_only(self):
        with patch.dict(os.environ, {
            "CHAINGUARD_ADMIN_USERNAME": "admin",
            "CHAINGUARD_ADMIN_PASSWORD": "test-password",
        }):
            response = self.client.post("/api/auth/login", json={
                "username": "admin", "password": "test-password",
            })
        self.assertEqual(response.status_code, 200)
        secret = "test-openai-key-do-not-return"
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "api_keys.py"
            with patch("src.api_key_config.API_KEYS_PATH", key_file), patch.dict(
                os.environ,
                {"OPENAI_API_KEY": ""},
            ):
                from src.api_key_config import get_api_key

                response = self.client.post(
                    "/api/settings/api-keys",
                    json={"keys": {"OPENAI_API_KEY": secret}},
                )

                self.assertEqual(response.status_code, 200)
                self.assertNotIn(secret, response.text)
                self.assertTrue(response.json()["configured"]["OPENAI_API_KEY"])
                self.assertIn("OPENAI_API_KEY =", key_file.read_text(encoding="utf-8"))
                self.assertIn(secret, key_file.read_text(encoding="utf-8"))
                with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                    self.assertEqual(get_api_key("OPENAI_API_KEY"), secret)

                removed = self.client.post(
                    "/api/settings/api-keys",
                    json={"keys": {"OPENAI_API_KEY": None}},
                )
                self.assertEqual(removed.status_code, 200)
                self.assertFalse(removed.json()["configured"]["OPENAI_API_KEY"])
                with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                    self.assertEqual(get_api_key("OPENAI_API_KEY"), "")

    def test_create_follow_up_and_private_model_history(self):
        chat = self.create()
        first = self.send(chat).json()
        self.assertEqual([m["role"] for m in first["messages"]], ["user", "assistant"])
        self.assertEqual(first["messages"][1]["text"], "A blockchain answer")
        self.assertNotIn('"tasks"', json.dumps(first))
        self.send(chat, "Explain that further")
        messages = self.complete.call_args.kwargs["messages"]
        self.assertEqual(messages[1]["content"], "What is a blockchain?")
        self.assertIn('"tasks"', messages[2]["content"])
        self.assertEqual(messages[3]["content"], "A blockchain answer")
        restored = self.client.get(f"/api/chats/{chat}").json()
        self.assertEqual(len(restored["messages"]), 4)
        self.assertEqual(self.client.get("/api/chats").json()["chats"][0]["id"], chat)

    def test_histories_are_isolated(self):
        first, second = self.create(), self.create()
        self.send(first, "First conversation")
        self.send(second, "Second conversation")
        messages = self.complete.call_args.kwargs["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[-1]["content"], "Second conversation")

    def test_browser_session_isolation(self):
        chat = self.create()
        cookie = self.client.cookies.get("chainguard_session")
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/chats").json()["chats"], [])
        self.assertEqual(self.client.get(f"/api/chats/{chat}").status_code, 404)
        self.assertEqual(self.send(chat).status_code, 404)
        self.client.cookies.clear()
        self.client.cookies.set("chainguard_session", cookie)
        self.assertEqual(self.client.get(f"/api/chats/{chat}").status_code, 200)

    def test_blank_and_oversized_input(self):
        chat = self.create()
        for text in ["", " \n ", "a" * 12001]:
            self.assertEqual(self.send(chat, text).status_code, 422)
        self.assertEqual(self.client.get(f"/api/chats/{chat}").json()["messages"], [])
        self.complete.assert_not_called()

    def test_attachment_limit_is_10_mib(self):
        attachment = InputAttachment(name="notes.txt", content="a" * MAX_ATTACHMENT_BYTES)
        self.assertEqual(len(attachment.content), 10 * 1024 * 1024)
        with self.assertRaises(ValueError):
            InputAttachment(name="notes.txt", content="a" * (MAX_ATTACHMENT_BYTES + 1))

    def test_commands_do_not_exit_or_change_provider(self):
        chat = self.create()
        self.assertIn("configured on the server", self.send(chat, "change ai").json()["messages"][-1]["text"])
        self.assertIn("Goodbye", self.send(chat, "quit").json()["messages"][-1]["text"])
        self.complete.assert_not_called()
        self.assertEqual(self.send(chat).status_code, 200)

    def test_unconfigured_provider_is_actionable(self):
        self.app.state.provider_error = "Set OPENAI_API_KEY before making an AI request."
        chat = self.create()
        response = self.send(chat)
        self.assertEqual(response.status_code, 503)
        self.assertIn("OPENAI_API_KEY", response.json()["detail"])
        self.assertFalse(self.client.get(f"/api/chats/{chat}").json()["processing"])

    def test_invalid_model_response_recovers_without_private_history(self):
        chat = self.create()
        self.complete.return_value = "not valid JSON"
        with self.assertLogs("src.api", level="ERROR"):
            result = self.send(chat).json()
        self.assertFalse(result["processing"])
        self.assertIn("Unable to complete", result["error"])
        self.complete.return_value = envelope(task())
        self.assertIsNone(self.send(chat).json()["error"])
        self.assertEqual(len(self.complete.call_args.kwargs["messages"]), 2)

    def test_processing_visible_and_overlapping_turn_rejected(self):
        entered, release = threading.Event(), threading.Event()

        def slow_model(**kwargs):
            entered.set()
            self.assertTrue(release.wait(10))
            return envelope(task())

        self.complete.side_effect = slow_model
        chat = self.create()
        with ThreadPoolExecutor() as pool:
            pending = pool.submit(self.send, chat)
            try:
                self.assertTrue(entered.wait(5))
                state = self.client.get(f"/api/chats/{chat}").json()
                self.assertTrue(state["processing"])
                self.assertEqual(len(state["messages"]), 1)
                self.assertEqual(self.send(chat).status_code, 409)
                other = self.create()
                self.assertNotEqual(other, chat)
            finally:
                release.set()
            self.assertFalse(pending.result(timeout=10).json()["processing"])

    def test_unique_downloads_and_partial_task_failure(self):
        self.complete.return_value = envelope(task("first"), task("fails"), task("third"))
        paths = []

        def execute(item, respond, output, **kwargs):
            if item.message == "fails":
                raise RuntimeError("fetch unavailable")
            path = Path(output)
            paths.append(path)
            path.write_text(json.dumps({"result": item.message}))
            respond(f"Requested information saved to {output}")

        with patch("src.api.execute_ba_task", side_effect=execute):
            first = self.create()
            result = self.send(first).json()
            self.complete.return_value = envelope(task("single"))
            self.send(first)
            self.send(self.create())
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(len(result["messages"]), 4)
        self.assertIn("fetch unavailable", result["messages"][2]["text"])
        self.assertNotIn(str(self.app.state.output_root), json.dumps(result))
        file = result["messages"][1]["attachments"][0]
        response = self.client.get(file["url"])
        self.assertEqual(response.json(), {"result": "first"})
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertEqual(self.client.get(f"/api/chats/{first}/files/unknown").status_code, 404)
        self.client.cookies.clear()
        self.assertEqual(self.client.get(file["url"]).status_code, 404)

    def test_each_download_is_snapshot_even_if_task_file_changes(self):
        def execute(item, respond, output, **kwargs):
            for result in ["resolver", "context"]:
                Path(output).write_text(json.dumps({"stage": result}))
                respond(f"Saved to {output}")

        with patch("src.api.execute_ba_task", side_effect=execute):
            result = self.send(self.create()).json()
        files = [m["attachments"][0] for m in result["messages"][1:]]
        self.assertEqual(self.client.get(files[0]["url"]).json(), {"stage": "resolver"})
        self.assertEqual(self.client.get(files[1]["url"]).json(), {"stage": "context"})

    def test_scam_check_download_has_descriptive_filename(self):
        address = "0x" + "1" * 40
        self.complete.return_value = envelope(task(
            None, request_type="scam_check", chain="ethereum",
            raw_input={"type": "address", "value": address},
            required_input_type="address_with_context",
            requested_fields=["contract", "tx_history", "tokens", "liquidity"],
        ))

        def execute(item, respond, output, **kwargs):
            Path(output).write_text(json.dumps({"address": address}))
            respond("Scam check complete.")

        with patch("src.api.execute_ba_task", side_effect=execute):
            reply = self.send(self.create(), "Is this token a scam?").json()["messages"][-1]

        self.assertEqual(reply["attachments"][0]["name"], f"scam-check-{address}.json")
        self.assertNotIn("scam-check-", reply["text"])

    def test_attached_json_target_can_drive_scam_check(self):
        address = "0x" + "2" * 40
        self.complete.return_value = envelope(task(
            None, request_type="scam_check", chain="ethereum",
            raw_input={"type": "address", "value": address},
            required_input_type="address_with_context",
            requested_fields=["contract", "tx_history", "tokens", "liquidity"],
        ))

        def execute(item, respond, output, **kwargs):
            self.assertEqual(item.request_type, "scam_check")
            self.assertEqual(item.raw_input.value, address)
            Path(output).write_text(json.dumps({"address": address}))
            respond("Scam check complete.")

        with patch("src.api.execute_ba_task", side_effect=execute):
            response = self.client.post(
                f"/api/chats/{self.create()}/messages",
                json={
                    "text": "",
                    "attachments": [{
                        "name": "token.json",
                        "content": json.dumps({"address": address}),
                    }],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"][-1]["text"], "Scam check complete.")
        model_messages = self.complete.call_args.kwargs["messages"]
        self.assertIn("ATTACHED JSON FILES", model_messages[0]["content"])
        self.assertIn(address, model_messages[-1]["content"])

    def test_backend_restart_expires_chats(self):
        chat = self.create()
        self.app.state.sessions = {}
        self.assertEqual(self.client.get("/api/chats").json()["chats"], [])
        self.assertEqual(self.client.get(f"/api/chats/{chat}").status_code, 404)

    def test_lookup_summary_named_download_and_follow_up_use_saved_evidence(self):
        address = "0x" + "1" * 40
        self.complete.return_value = envelope(task(
            None, request_type="address_info", chain="ethereum",
            raw_input={"type": "address", "value": address},
            required_input_type="address", requested_fields=["tx_history"],
        ))
        fetch_result = ({"transactions": {"status": "pass", "data": [
            {"hash": "0xabc", "from": address, "to": address, "value_wei": "42"}
        ], "error": None}}, {"chain_family": "evm", "address_type": "unknown"})
        with patch("src.main.fetch_results", return_value=fetch_result) as fetcher, patch(
            "agents.fi.complete", side_effect=[
                json.dumps({
                    "explanation": "Found one transaction: 0xabc. "
                    "Filename suggestion: wallet-transactions.json",
                    "filename": "../../wallet-transactions.json",
                }),
                json.dumps({"explanation": "The notable transaction is 0xabc, value 42.", "filename": "wallet-transactions.json"}),
            ],
        ) as investigator:
            chat = self.create()
            result = self.send(chat, "Show transaction history").json()
            reply = result["messages"][-1]
            self.assertEqual(reply["text"], "Found one transaction: 0xabc.")
            file = reply["attachments"][0]
            self.assertEqual(file["name"], "wallet-transactions.json")
            downloaded = self.client.get(file["url"])
            self.assertEqual(downloaded.json()["tx_history"][0]["hash"], "0xabc")
            self.assertIn("wallet-transactions.json", downloaded.headers["content-disposition"])
            self.complete.return_value = envelope(task(
                None, request_type="address_info", use_saved_lookup=True,
            ))
            follow_up = self.send(chat, "What transactions are notable?").json()["messages"][-1]
            self.assertIn("0xabc", follow_up["text"])
            self.assertEqual(follow_up["attachments"], [])
            fetcher.assert_called_once()
            evidence = json.loads(investigator.call_args.kwargs["messages"][-1]["content"])
            self.assertEqual(evidence["lookups"][0]["tx_history"][0]["hash"], "0xabc")
            self.assertNotIn("Saved lookup evidence", json.dumps(result))

    def test_lookup_analysis_failure_keeps_download_and_evidence(self):
        self.complete.return_value = envelope(task(
            None, request_type="address_info", chain="ethereum",
            raw_input={"type": "address", "value": "0x" + "1" * 40},
            requested_fields=["tx_history"],
        ))
        with patch("src.main.fetch_results", return_value=(
            {"transactions": {"status": "fail", "data": None, "error": "API unavailable"}},
            {"chain_family": "evm"},
        )), patch("agents.fi.complete", side_effect=ValueError("Provider unavailable")):
            reply = self.send(self.create()).json()["messages"][-1]
        self.assertIn("analysis is currently unavailable", reply["text"])
        data = self.client.get(reply["attachments"][0]["url"]).json()
        self.assertEqual(data["fetcher_provenance"]["tx_history_fetcher"]["status"], "fail")

    def test_cli_uses_shared_service_and_keeps_terminal_reply(self):
        history = []
        output = io.StringIO()
        with patch("src.main.DEV_MODE", True), redirect_stdout(output):
            handle_ba_request("What is blockchain?", history)
        self.assertIn("Response:\nA blockchain answer", output.getvalue())
        self.assertEqual(history[-1], {"role": "assistant", "content": "A blockchain answer"})


if __name__ == "__main__":
    unittest.main()
