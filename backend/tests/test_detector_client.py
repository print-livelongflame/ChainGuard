"""Unit tests for the ChainGuard-to-detector HTTP contract."""
import json
from urllib.error import HTTPError, URLError
from unittest.mock import MagicMock

import pytest

import detector_integration.client as client
from src.detector_config import DetectorConfig


@pytest.fixture

def configured_detector(monkeypatch):
    config = DetectorConfig(
        enabled=True,
        endpoint="http://detector.test/detect",
    )
    monkeypatch.setattr(client, "load_detector_config", lambda: config)
    monkeypatch.setattr(
        client,
        "get_api_key",
        lambda name: "test-detector-key",
    )
    return config


def response_with_body(body: bytes):
    response = MagicMock()
    response.__enter__.return_value = response
    response.read.return_value = body
    return response


def test_call_detector_sends_request_and_validates_response(
    configured_detector,
    monkeypatch,
):
    payload = {
        "label": "insufficient_evidence",
        "risk_type": "unknown",
        "confidence": 0.0,
        "evidence": [],
    }
    response = response_with_body(json.dumps(payload).encode())
    urlopen = MagicMock(return_value=response)
    monkeypatch.setattr(client, "urlopen", urlopen)

    result = client.call_detector(
        client.AddressContext(
            address="0x0000000000000000000000000000000000000001",
            chain="ethereum",
        )
    )

    request = urlopen.call_args.args[0]
    assert request.full_url == str(configured_detector.endpoint)
    assert request.get_header("X-api-key") == "test-detector-key"
    assert json.loads(request.data)["chain"] == "ethereum"
    assert urlopen.call_args.kwargs["timeout"] == 60
    assert result.label == "insufficient_evidence"


def test_call_detector_rejects_missing_configuration(monkeypatch):
    monkeypatch.setattr(client, "load_detector_config", lambda: None)
    urlopen = MagicMock()
    monkeypatch.setattr(client, "urlopen", urlopen)

    with pytest.raises(ValueError, match="No external detector is configured"):
        client.call_detector(client.AddressContext(address="0x123"))

    urlopen.assert_not_called()


@pytest.mark.parametrize(
    ("network_error", "message"),
    [
        (
            HTTPError("http://detector.test/detect", 503, "unavailable", None, None),
            "returned HTTP 503",
        ),
        (URLError("connection refused"), "could not be reached"),
    ],
)
def test_call_detector_reports_transport_errors(
    configured_detector,
    monkeypatch,
    network_error,
    message,
):
    monkeypatch.setattr(
        client,
        "urlopen",
        MagicMock(side_effect=network_error),
    )

    with pytest.raises(ValueError, match=message):
        client.call_detector(client.AddressContext(address="0x123"))


def test_call_detector_rejects_invalid_json(configured_detector, monkeypatch):
    response = response_with_body(b"{invalid json")
    monkeypatch.setattr(
        client,
        "urlopen",
        MagicMock(return_value=response),
    )

    with pytest.raises(ValueError, match="returned invalid JSON"):
        client.call_detector(client.AddressContext(address="0x123"))


def test_call_detector_rejects_response_with_invalid_schema(
    configured_detector,
    monkeypatch,
):
    response = response_with_body(
        json.dumps({"label": "probably_scam"}).encode()
    )
    monkeypatch.setattr(
        client,
        "urlopen",
        MagicMock(return_value=response),
    )

    with pytest.raises(ValueError, match="returned an invalid result"):
        client.call_detector(client.AddressContext(address="0x123"))
