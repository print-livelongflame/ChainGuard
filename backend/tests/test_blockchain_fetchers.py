"""Etherscan response tests with no live API requests."""
from unittest.mock import MagicMock

import pytest
import requests

from fetchers import token_info_fetcher, transaction_history_fetcher


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(transaction_history_fetcher, "get_api_key", lambda _: "test-key")
    monkeypatch.setattr(token_info_fetcher, "get_api_key", lambda _: "test-key")


def fake_response(monkeypatch, module, payload):
    response = MagicMock()
    response.json.return_value = payload
    get = MagicMock(return_value=response)
    monkeypatch.setattr(module.requests, "get", get)
    return get


def test_transactions_normalize_direction_and_value(monkeypatch):
    incoming = {"hash": "in", "from": "0xDEF", "to": "0xabc", "value": str(2 * 10**18)}
    outgoing = {"hash": "out", "from": "0xABC", "to": "0xDEF", "value": "0"}
    get = fake_response(monkeypatch, transaction_history_fetcher,
                        {"status": "1", "result": [incoming, outgoing]})
    result = transaction_history_fetcher.get_transactions("0xABC", chain_id=56)
    assert [tx["direction"] for tx in result] == ["incoming", "outgoing"]
    assert result[0]["value_native"] == 2
    assert get.call_args.kwargs["params"]["chainid"] == 56
    assert get.call_args.kwargs["params"]["apikey"] == "test-key"
    assert get.call_args.kwargs["timeout"] == 10


def test_transactions_accept_explicit_empty_history(monkeypatch):
    fake_response(monkeypatch, transaction_history_fetcher,
                  {"status": "0", "message": "No transactions found", "result": []})
    assert transaction_history_fetcher.get_transactions("0xABC") == []


@pytest.mark.parametrize("payload", [
    {"status": "0", "message": "NOTOK", "result": "Max rate limit reached"},
    {"status": "1", "result": "not a list"},
    ["not an object"],
])
def test_transactions_reject_api_and_shape_errors(monkeypatch, payload):
    fake_response(monkeypatch, transaction_history_fetcher, payload)
    with pytest.raises(ValueError, match="Etherscan"):
        transaction_history_fetcher.get_transactions("0xABC")


def test_transactions_propagate_http_failure(monkeypatch):
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("503 unavailable")
    monkeypatch.setattr(transaction_history_fetcher.requests, "get", lambda *a, **kw: response)
    with pytest.raises(requests.HTTPError, match="503"):
        transaction_history_fetcher.get_transactions("0xABC")
    response.json.assert_not_called()


def test_token_info_normalizes_transfers(monkeypatch):
    get = fake_response(monkeypatch, token_info_fetcher,
                        {"status": "1", "result": [{"hash": "tx-1"}, {"hash": "tx-2"}]})
    result = token_info_fetcher.get_token_info("0xABC", chain_id=56)
    assert result["token_transfer_count"] == 2
    assert result["token_transfers"][0]["hash"] == "tx-1"
    assert get.call_args.kwargs["params"]["action"] == "tokentx"
    assert get.call_args.kwargs["params"]["chainid"] == 56


def test_token_info_skips_api_without_key(monkeypatch):
    monkeypatch.setattr(token_info_fetcher, "get_api_key", lambda _: None)
    get = MagicMock()
    monkeypatch.setattr(token_info_fetcher.requests, "get", get)
    assert "API key is missing" in token_info_fetcher.get_token_info("0xABC")["error"]
    get.assert_not_called()


def test_token_info_reports_invalid_key(monkeypatch):
    fake_response(monkeypatch, token_info_fetcher,
                  {"status": "0", "message": "NOTOK", "result": "Missing/Invalid API Key"})
    assert "missing or invalid" in token_info_fetcher.get_token_info("0xABC")["error"]
