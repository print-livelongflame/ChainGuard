"""Validate the contract between fetched evidence and detector results."""
import pytest
from pydantic import ValidationError

from src.schema import AddressContext, ContractAddressMatch, DetectionResult


def valid_result():
    return {
        "label": "scam",
        "risk_type": "liquidity_risk",
        "confidence": 0.8,
        "evidence": [{"description": "Liquidity removed", "weight": 0.7}],
    }


def test_valid_detection_result_preserves_evidence():
    result = DetectionResult.model_validate(valid_result())
    assert result.evidence[0].description == "Liquidity removed"
    assert result.evidence[0].weight == 0.7


@pytest.mark.parametrize("field,value", [
    ("label", "probably_scam"),
    ("confidence", -0.1),
    ("confidence", 1.1),
    ("risk_type", ""),
])
def test_detection_result_rejects_invalid_assessment(field, value):
    payload = valid_result()
    payload[field] = value
    with pytest.raises(ValidationError):
        DetectionResult.model_validate(payload)


@pytest.mark.parametrize("evidence", [
    [{"description": "", "weight": 0.7}],
    [{"description": "Liquidity removed", "weight": -0.1}],
    [{"description": "Liquidity removed", "weight": 1.1}],
    [{"description": "Liquidity removed", "weight": 0.7, "fabricated": True}],
])
def test_detection_result_rejects_invalid_evidence(evidence):
    payload = valid_result()
    payload["evidence"] = evidence
    with pytest.raises(ValidationError):
        DetectionResult.model_validate(payload)


def test_detection_result_requires_evidence_field():
    payload = valid_result()
    del payload["evidence"]
    with pytest.raises(ValidationError):
        DetectionResult.model_validate(payload)


def test_address_context_keeps_fetcher_provenance():
    context = AddressContext.model_validate({
        "address": "0xabc",
        "fetcher_provenance": {
            "contract": {"fields": ["verified_source"], "status": "fail", "error": "timeout"}
        },
    })
    assert context.fetcher_provenance["contract"].status == "fail"
    assert context.fetcher_provenance["contract"].error == "timeout"
    assert context.tx_history == []


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_contract_match_rejects_out_of_range_score(score):
    with pytest.raises(ValidationError):
        ContractAddressMatch.model_validate({
            "contract_address": "0xabc", "match_score": score, "match_quality": "exact"
        })
