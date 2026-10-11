"""Offline checks for the remaining transaction and liquidity HTTP fetchers."""
from unittest.mock import MagicMock

import pytest
import requests

from fetchers import liquidty_pairedPool_fetcher as liquidity
from fetchers import tx_hash_fetcher


def test_transaction_hash_uses_etherscan_and_extracts_addresses(monkeypatch):
    transaction = {"hash": "0xhash", "from": "0xsender", "to": "0xrecipient", "value": "0x10"}
    response = MagicMock()
    response.json.return_value = {"result": transaction}
    get = MagicMock(return_value=response)
    monkeypatch.setattr(tx_hash_fetcher, "get_api_key", lambda _: "test-key")
    monkeypatch.setattr(tx_hash_fetcher.requests, "get", get)

    result = tx_hash_fetcher.get_transaction_by_hash("0xhash", chain_id=56)

    assert result == transaction
    assert tx_hash_fetcher.extract_addresses(result) == {
        "transaction_hash": "0xhash", "from": "0xsender", "to": "0xrecipient",
    }
    assert get.call_args.kwargs["params"]["chainid"] == 56
    assert get.call_args.kwargs["params"]["apikey"] == "test-key"
    assert get.call_args.kwargs["timeout"] == 10


def test_transaction_hash_rejects_missing_result(monkeypatch):
    response = MagicMock()
    response.json.return_value = {"result": None}
    monkeypatch.setattr(tx_hash_fetcher.requests, "get", lambda *a, **kw: response)
    with pytest.raises(Exception, match="No transaction found"):
        tx_hash_fetcher.get_transaction_by_hash("0xmissing")


def test_liquidity_normalizes_pool_data(monkeypatch):
    response = MagicMock()
    response.json.return_value = {"pairs": [{
        "pairAddress": "0xpool", "dexId": "uniswap",
        "baseToken": {"symbol": "EX"}, "quoteToken": {"symbol": "WETH"},
        "liquidity": {"usd": 1250},
    }]}
    get = MagicMock(return_value=response)
    monkeypatch.setattr(liquidity.requests, "get", get)

    result = liquidity.get_liquidity("0xtoken")

    assert result == [{
        "pool_address": "0xpool", "dex": "uniswap", "token_pair": ["EX", "WETH"],
        "liquidity_usd": 1250,
    }]
    assert get.call_args.args[0].endswith("/0xtoken")
    assert get.call_args.kwargs["timeout"] == 10


def test_liquidity_propagates_http_failure(monkeypatch):
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError("503 unavailable")
    monkeypatch.setattr(liquidity.requests, "get", lambda *a, **kw: response)
    with pytest.raises(requests.HTTPError, match="503"):
        liquidity.get_liquidity("0xtoken")
    response.json.assert_not_called()
