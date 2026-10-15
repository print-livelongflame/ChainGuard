"""Tests for task-specific initial LLM output budgets."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agents import ba, fi, sch
from src.llm_provider import OUTPUT_TOKEN_BUDGETS
from src.schema import AddressContext, DetectionResult


@pytest.mark.parametrize(
    ("prompt", "budget"),
    [
        ("Who are you?", "identity_basic_faq"),
        ("What is ChainGuard?", "identity_basic_faq"),
        ("what is rug pull?", "general_explanation"),
        (
            "can u check if this token is a scam "
            "0x906CC2Ad139eb6637e28605F908903C8aDCe566A?",
            "scam_investigation",
        ),
        (
            "Summarize this address "
            "0x906CC2Ad139eb6637e28605F908903C8aDCe566A",
            "address_summary",
        ),
        ("What is a rug pull in tokens?", "general_explanation"),
        (
            "Explain why this token is a rug pull.",
            "scam_investigation",
        ),
    ],
)
def test_business_analyser_selects_task_budget(prompt, budget):
    assert ba.initial_output_budget(prompt) == OUTPUT_TOKEN_BUDGETS[budget]


def test_business_analyser_passes_selected_budget_to_provider(monkeypatch):
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

    assert completion.call_args.kwargs["max_tokens"] == 80


def test_scam_checker_uses_scam_investigation_budget(monkeypatch):
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

    assert completion.call_args.kwargs["max_tokens"] == 350


def test_forensic_lookup_uses_address_summary_budget(monkeypatch):
    completion = MagicMock(
        return_value=json.dumps(
            {"explanation": "Lookup summary.", "filename": "address-summary.json"}
        )
    )
    monkeypatch.setattr(fi, "complete", completion)

    fi.analyze_lookup([], "Summarize this address.")

    assert completion.call_args.kwargs["max_tokens"] == 250


def test_forensic_detector_explanation_uses_scam_budget(monkeypatch):
    completion = MagicMock(return_value="The detector found limited evidence.")
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

    assert completion.call_args.kwargs["max_tokens"] == 350
