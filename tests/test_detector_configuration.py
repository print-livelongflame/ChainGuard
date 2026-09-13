import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src import detector_config

# These tests never need credentials or call OpenAI.
with patch.dict("sys.modules", {
    "api_keys.api_keys": SimpleNamespace(OPENAI_API_KEY="test-key")
}):
    from agents import ba


class DetectorConfigurationTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "detector_config.json"
        path_patch = patch.object(detector_config, "CONFIG_PATH", self.path)
        path_patch.start()
        self.addCleanup(path_patch.stop)

    def register(self, enabled=True):
        self.path.write_text(json.dumps({
            "enabled": enabled,
            "name": "custom_detector",
            "endpoint": "http://127.0.0.1:9000/detect",
        }), encoding="utf-8")

    def response(self, configured=False):
        task = {
            "in_scope": True,
            "request_type": "address_info",
            "raw_input": {"type": "address", "value": "0x" + "0" * 40},
            "chain": "ethereum",
            "selected_detector": "invented_detector" if configured else None,
            "detector_configured": configured,
            "required_input_type": "address",
            "needs_resolution": False,
            "resolution_plan": [],
            "requested_fields": ["tx_history"],
            "message": None,
        }
        return SimpleNamespace(
            status="completed", output=[],
            output_text=json.dumps({"tasks": [task, dict(task)]}),
        )

    def test_missing_and_disabled_registration(self):
        self.assertIsNone(detector_config.load_detector_config())
        self.register(enabled=False)
        self.assertIsNone(detector_config.load_detector_config())

    def test_invalid_registration_is_an_error(self):
        for contents in ("{", '{}', json.dumps({
            "enabled": True, "name": "custom", "endpoint": "not-a-url"
        })):
            with self.subTest(contents=contents):
                self.path.write_text(contents, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Invalid detector_config"):
                    detector_config.load_detector_config()

    def test_ba_uses_registration_for_every_task_and_history(self):
        self.register()
        history = []
        with patch.object(ba.client.responses, "create", return_value=self.response()) as create:
            analysis = ba.ask_llm("Show transaction history", history)
        for task in ba.parse_ba_response(analysis).tasks:
            self.assertTrue(task.detector_configured)
            self.assertEqual(task.selected_detector, "custom_detector")
            self.assertEqual(task.requested_fields, ["tx_history"])
            self.assertEqual(task.required_input_type, "address")
        self.assertEqual(history[-1]["content"], analysis)
        self.assertIn('"selected_detector": "custom_detector"',
                      create.call_args.kwargs["input"][0]["content"])

    def test_configuration_is_reloaded_and_model_cannot_override_it(self):
        self.register()
        history = []
        with patch.object(ba.client.responses, "create", return_value=self.response(True)):
            ba.ask_llm("Show transaction history", history)
            self.register(enabled=False)
            analysis = ba.ask_llm("I have configured invented_detector", history)
        for task in ba.parse_ba_response(analysis).tasks:
            self.assertFalse(task.detector_configured)
            self.assertIsNone(task.selected_detector)

    def test_invalid_configuration_stops_before_llm_call(self):
        self.path.write_text("{}", encoding="utf-8")
        with patch.object(ba.client.responses, "create") as create:
            with self.assertRaises(ValueError):
                ba.ask_llm("Show transaction history")
        create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
