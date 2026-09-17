import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pydantic import ValidationError

with patch.dict("sys.modules", {
    "api_keys.api_keys": SimpleNamespace(OPENAI_API_KEY="test-key")
}):
    from agents import ba, sch
    from src import main, context_builder

from detector_template.schema import AddressContext
from detector_template.detector import detect
from src.detector_config import DetectorConfig, detector_metadata


ADDRESS = "0x" + "1" * 40


def task(**overrides):
    data = dict(
        in_scope=True, request_type="scam_check",
        raw_input={"type": "address", "value": ADDRESS}, chain="ethereum",
        selected_detector=None, detector_configured=False,
        required_input_type="address_with_context", needs_resolution=False,
        resolution_plan=[], requested_fields=list(ba.CONTEXT_FIELDS), message=None,
    )
    data.update(overrides)
    return ba.BAOutput.model_validate(data)


def assessment(**overrides):
    data = dict(
        label="insufficient_evidence", risk_type="unknown", confidence=0.0,
        evidence=[{"description": "Contract fetch failed; other context is empty.", "weight": 0.8}],
        explanation="The supplied context is insufficient to determine whether this is a scam.",
        reasoning_trace=None,
    )
    data.update(overrides)
    return data


def response(data=None, **overrides):
    values = dict(status="completed", output=[], output_text=json.dumps(data or assessment()))
    values.update(overrides)
    return SimpleNamespace(**values)


class ScamCheckerTests(unittest.TestCase):
    def test_contract_rejects_old_labels_and_unstructured_evidence(self):
        for changes in (
            {"label": "high_risk"}, {"evidence": ["unverified"]},
            {"confidence": 1.1}, {"confidence": "0.5"},
            {"evidence": [{"description": "test", "weight": -0.1}]},
            {"risk_type": None}, {"unexpected": True},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                sch.parse_scam_checker_response(json.dumps(assessment(**changes)))
        for label in ("scam", "not_scam", "insufficient_evidence"):
            parsed = sch.parse_scam_checker_response(json.dumps(assessment(label=label)))
            self.assertEqual(parsed.label, label)
            self.assertNotIn("detection_result", parsed.model_dump())

    def test_fallback_pipeline_uses_only_four_fetchers_and_displays_contract(self):
        def fetch(name, *args, **kwargs):
            if name == "contract":
                return {"status": "fail", "data": None, "error": "unavailable"}
            return {"status": "pass", "data": {} if name == "token_info" else [], "error": None}

        history = []
        cli_output = io.StringIO()
        with TemporaryDirectory() as directory, \
                patch.object(main, "run_fetcher", side_effect=fetch) as fetcher, \
                patch.object(sch.client.responses, "create", return_value=response()) as create, \
                patch.object(main, "ask_llm", return_value=json.dumps({"tasks": [task().model_dump()]})), \
                contextlib.redirect_stdout(cli_output):
            path = Path(directory) / "info.json"
            with patch.object(main, "JSON_FILE", str(path)):
                main.handle_ba_request("Is this address a scam?", history)
            context = json.loads(path.read_text())
        self.assertEqual({call.args[0] for call in fetcher.call_args_list},
                         {"contract", "transactions", "token_info", "liquidity"})
        self.assertEqual(context["contract"], {})
        self.assertEqual(context["fetcher_provenance"]["contract_fetcher"]["status"], "fail")
        self.assertNotIn("honeypot", context)
        self.assertNotIn("rugcheck", context)
        create.assert_called_once()
        payload = json.loads(create.call_args.kwargs["input"][1]["content"])
        self.assertEqual(payload["task"]["request_type"], "scam_check")
        self.assertEqual(payload["address_context"]["address"], ADDRESS)
        output = cli_output.getvalue().split("Scam Checker output:", 1)[1]
        self.assertIn("Source: Scam Checker LLM", output)
        shown = json.loads(output[output.index("{"):output.rindex("}") + 1])
        self.assertEqual(shown, {k: v for k, v in assessment().items() if v is not None})
        self.assertEqual(output.split("Response:\n", 1)[1].strip(), assessment()["explanation"])
        self.assertEqual(history[-1], {"role": "assistant", "content": assessment()["explanation"]})
        schema = create.call_args.kwargs["text"]["format"]["schema"]
        for obj in (schema, schema["$defs"]["EvidenceItem"]):
            self.assertFalse(obj["additionalProperties"])
            self.assertEqual(set(obj["required"]), set(obj["properties"]))

    def test_configured_detector_is_placeholder_without_fetch_or_sch(self):
        for required in ("address", "address_with_context"):
            messages = []
            with patch.object(main, "fetch_results") as fetch, \
                    patch.object(main, "assess_saved_context") as assess:
                main.execute_ba_task(task(detector_configured=True,
                    selected_detector="custom", required_input_type=required), messages.append)
            fetch.assert_not_called()
            assess.assert_not_called()
            self.assertIn("Integration not implemented yet", messages[-1])

    def test_other_branches_and_clarification_do_not_call_sch(self):
        cases = [task(request_type="general_question", message="A blockchain is a ledger."),
                 task(in_scope=False, message="Outside scope."),
                 task(raw_input=None, message="Which address?"),
                 task(request_type="address_info", requested_fields=["tx_history"])]
        for current in cases:
            with self.subTest(current=current.request_type), \
                    patch.object(main, "assess_saved_context") as assess, \
                    patch.object(main, "fetch_results", return_value=({}, {"chain_family": "evm", "address_type": "unknown"})), \
                    patch.object(main, "save_info"), contextlib.redirect_stdout(io.StringIO()):
                main.execute_ba_task(current, lambda message: None)
            assess.assert_not_called()

    def test_sch_rejects_ineligible_task_even_if_called_directly(self):
        with patch.object(sch.client.responses, "create") as create:
            for current in (task(detector_configured=True, selected_detector="custom"),
                            task(request_type="address_info")):
                with self.assertRaises(ValueError):
                    sch.ask_scam_checker(AddressContext(address=ADDRESS), current)
        create.assert_not_called()

    def test_ambiguous_target_does_not_reuse_saved_context(self):
        current = task(raw_input={"type": "token_name", "value": "TOKEN"},
                       needs_resolution=True, resolution_plan=["token_name_resolver_fetcher"])
        lookup = {"results": {"contract_address": {"status": "pass", "data": {
            "status": "ambiguous", "matches": [{"contract_address": ADDRESS}]
        }}}}
        messages = []
        with patch.object(main, "fetch_contract_address_results", return_value=lookup), \
                patch.object(main, "save_contract_address_info"), \
                patch.object(main, "assess_saved_context") as assess:
            main.execute_ba_task(current, messages.append)
        assess.assert_not_called()
        self.assertIn("exact contract address", messages[-1])

    def test_provider_failure_and_invalid_json_are_not_verdicts(self):
        failures = [response(status="failed"),
                    response(status="incomplete", incomplete_details=SimpleNamespace(reason="max_output_tokens")),
                    response(output=[SimpleNamespace(type="message", content=[SimpleNamespace(type="refusal", refusal="declined")])]),
                    response(output_text="not JSON")]
        for failure in failures:
            with self.subTest(failure=failure.status), \
                    patch.object(sch.client.responses, "create", return_value=failure), \
                    self.assertRaises(ValueError):
                sch.ask_scam_checker(AddressContext(address=ADDRESS), task())
        messages = []
        with patch.object(main, "assess_saved_context", side_effect=RuntimeError("provider unavailable")):
            main.run_scam_check(task(), "unused", messages.append)
        self.assertIn("assessment unavailable", messages[-1])
        self.assertNotIn('"label"', messages[-1])

    def test_saved_context_validation(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "info.json"
            for contents in ("{", '{}', '{"address":"x","liquidity":{}}'):
                path.write_text(contents)
                with self.assertRaises(ValueError):
                    sch.load_context(path)
            with self.assertRaises(ValueError):
                sch.load_context(Path(directory) / "missing.json")

    def test_ba_overrides_model_detector_claims_and_input_requirements(self):
        config = DetectorConfig(enabled=True, name="real", endpoint="http://localhost:9000/detect",
                                required_input_type="address")
        for selected in (config, None):
            model_task = task(detector_configured=selected is None, selected_detector="invented",
                              required_input_type="address")
            with patch.object(ba, "load_detector_config", return_value=selected), \
                    patch.object(ba.client.responses, "create", return_value=response({"tasks": [model_task.model_dump()]})):
                actual = ba.parse_ba_response(ba.ask_llm("Check this address")).tasks[0]
            self.assertEqual(actual.detector_configured, selected is not None)
            self.assertEqual(actual.selected_detector, "real" if selected else None)
            self.assertEqual(actual.required_input_type, "address" if selected else "address_with_context")
            self.assertEqual(actual.requested_fields, [] if selected else list(ba.CONTEXT_FIELDS))
        self.assertEqual(detector_metadata(config)["required_input_type"], "address")

    def test_template_and_builder_use_shared_contract(self):
        with patch.object(context_builder, "fetch_results", return_value=({}, {"chain_family": "evm"})):
            context = context_builder.build_address_context(ADDRESS)
        self.assertEqual(context.tx_history, [])
        self.assertEqual(context.tokens, [])
        self.assertEqual(context.liquidity, [])
        result = detect(context)
        self.assertEqual(result.label, "insufficient_evidence")
        self.assertEqual(result.evidence[0].weight, 0.0)


if __name__ == "__main__":
    unittest.main()
