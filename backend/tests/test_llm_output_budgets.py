"""Tests that agent requests do not impose output token caps."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from agents import ba, fi, sch
from src.schema import AddressContext, DetectionResult


def test_business_analyser_does_not_set_an_output_token_cap(monkeypatch):
    analysis = {
        "tasks": [
            {
                "in_scope": False,
                "request_type": "general_question",
                "raw_input": None,
                "chain": None,
                "selected_detector": None,
                "detector_configured": False,
                "required_input_type": None,
                "needs_resolution": False,
                "resolution_plan": [],
                "requested_fields": [],
                "message": "I am ChainGuard.",
            }
        ]
    }
    completion = MagicMock(return_value=json.dumps(analysis))
    monkeypatch.setattr(ba, "load_detector_config", lambda: None)
    def fake_detector_metadata(config):
        assert config is None
        return {
            "selected_detector": None,
            "detector_configured": False,
            "required_input_type": None,
        }

    monkeypatch.setattr(ba, "detector_metadata", fake_detector_metadata)
    monkeypatch.setattr(ba, "complete", completion)

    ba.ask_llm("Who are you?")

    assert "max_tokens" not in completion.call_args.kwargs
    assert "budget" not in completion.call_args.kwargs["messages"][0]["content"]


def test_scam_checker_does_not_set_an_output_token_cap(monkeypatch):
    completion = MagicMock(
        return_value=json.dumps(
            {
                "label": "insufficient_evidence",
                "risk_type": "unknown",
                "confidence": 0.2,
                "evidence": [],
                "explanation": "There is not enough evidence.",
            }
        )
    )
    monkeypatch.setattr(sch, "complete", completion)

    sch.ask_scam_checker(AddressContext(address="0x906CC2Ad139eb6637e28605F908903C8aDCe566A"))

    assert "max_tokens" not in completion.call_args.kwargs


def test_forensic_lookup_does_not_set_an_output_token_cap(monkeypatch):
    completion = MagicMock(
        return_value=json.dumps(
            {"explanation": "Lookup summary.", "filename": "address-summary.json"}
        )
    )
    monkeypatch.setattr(fi, "complete", completion)

    fi.analyze_lookup([], "Summarize this address.")

    assert "max_tokens" not in completion.call_args.kwargs


def test_forensic_detector_explanation_does_not_set_an_output_token_cap(monkeypatch):
    completion = MagicMock(return_value=json.dumps({
        "explanation": "The detector found limited evidence.", "followups": [],
    }))
    monkeypatch.setattr(fi, "complete", completion)
    monkeypatch.setattr(
        fi,
        "load_detector_config",
        lambda: SimpleNamespace(name="Test detector", is_llm_based=False),
    )
    result = DetectionResult(
        label="insufficient_evidence",
        risk_type="unknown",
        confidence=0.2,
        evidence=[],
    )

    fi.explain_detector_result(result)

    assert "max_tokens" not in completion.call_args.kwargs
