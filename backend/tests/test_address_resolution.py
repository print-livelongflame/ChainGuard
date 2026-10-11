"""Offline contract-address resolution checks using small token-list fixtures."""
import json
import time
from unittest.mock import MagicMock

import pytest
import requests

from fetchers import contract_address_fetcher as resolver


ADDRESS_A = "0x" + "a" * 40
ADDRESS_B = "0x" + "b" * 40


def token(name, symbol, address):
    return {"name": name, "symbol": symbol, "platforms": {"ethereum": address}}


@pytest.fixture
def token_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(resolver, "CACHE_FOLDER", str(tmp_path))
    return tmp_path


def test_resolver_requires_a_query_and_supported_chain(monkeypatch):
    get = MagicMock()
    monkeypatch.setattr(resolver.requests, "get", get)
    assert "required" in resolver.resolve_contract_address("", "")["error"]
    assert "Unsupported chain_id" in resolver.resolve_contract_address("Token", chain_id=999)["error"]
    get.assert_not_called()


def test_matching_uses_token_name_and_symbol_without_guessing(token_cache, monkeypatch):
    tokens = [token("Example Token", "EXT", ADDRESS_A), token("Example Token", "EXT", ADDRESS_B)]
    monkeypatch.setattr(resolver, "fetch_coingecko_token_list", lambda *a, **kw: (tokens, {"source": "cache"}))
    monkeypatch.setattr(resolver, "get_api_key", lambda _: "")
    get = MagicMock()
    monkeypatch.setattr(resolver.requests, "get", get)

    result = resolver.resolve_contract_address("Example Token", "EXT")

    assert result["status"] == "ambiguous"
    assert [match["contract_address"] for match in result["matches"]] == [ADDRESS_A, ADDRESS_B]
    assert result["matches"][0]["match_quality"] == "exact_name_and_symbol"
    assert all(match["etherscan_verification"] == "skipped_missing_api_key" for match in result["matches"])
    get.assert_not_called()


def test_etherscan_verifies_bytecode_and_reports_invalid_key(monkeypatch):
    tokens = [token("Example", "EX", ADDRESS_A), token("Example", "EX", ADDRESS_B)]
    monkeypatch.setattr(resolver, "fetch_coingecko_token_list", lambda *a, **kw: (tokens, {}))
    monkeypatch.setattr(resolver, "get_api_key", lambda _: "test-key")
    responses = []
    for payload in ({"result": "0x6000"}, {"message": "Missing/Invalid API Key", "result": "NOTOK"}):
        response = MagicMock()
        response.json.return_value = payload
        responses.append(response)
    get = MagicMock(side_effect=responses)
    monkeypatch.setattr(resolver.requests, "get", get)

    result = resolver.resolve_contract_address("Example", "EX")

    assert [match["etherscan_verification"] for match in result["matches"]] == ["verified", "failed"]
    assert "missing or invalid" in result["matches"][1]["verification_error"]
    assert get.call_count == 2
    assert get.call_args_list[0].kwargs["params"]["address"] == ADDRESS_A
    assert all(call.kwargs["timeout"] == 10 for call in get.call_args_list)


def test_fresh_token_list_cache_avoids_network(token_cache, monkeypatch):
    tokens = [token("Example", "EX", ADDRESS_A)]
    resolver.write_token_list_cache("ethereum", tokens)
    get = MagicMock()
    monkeypatch.setattr(resolver.requests, "get", get)

    loaded, info = resolver.fetch_coingecko_token_list("ethereum")

    assert loaded == tokens
    assert info["source"] == "cache"
    get.assert_not_called()


def test_stale_token_list_is_used_when_refresh_fails(token_cache, monkeypatch):
    path = resolver.get_cache_path("ethereum")
    with open(path, "w", encoding="utf-8") as cache_file:
        json.dump({"fetched_at": time.time() - resolver.CACHE_TTL_SECONDS - 60,
                   "tokens": [token("Example", "EX", ADDRESS_A)]}, cache_file)
    get = MagicMock(side_effect=requests.Timeout("CoinGecko timed out"))
    monkeypatch.setattr(resolver.requests, "get", get)

    loaded, info = resolver.fetch_coingecko_token_list("ethereum")

    assert loaded[0]["platforms"]["ethereum"] == ADDRESS_A
    assert info["source"] == "stale_cache"
    assert "timed out" in info["refresh_error"]


def test_refresh_rejects_non_list_response(token_cache, monkeypatch):
    response = MagicMock()
    response.json.return_value = {"error": "unexpected format"}
    monkeypatch.setattr(resolver.requests, "get", lambda *a, **kw: response)

    with pytest.raises(ValueError, match="not a list"):
        resolver.fetch_coingecko_token_list("ethereum")


def test_missing_and_invalid_cache_entries_require_refresh(token_cache, monkeypatch):
    missing, info = resolver.read_token_list_cache("ethereum")
    assert missing is None and info["source"] == "missing"
    path = resolver.get_cache_path("ethereum")
    with open(path, "w", encoding="utf-8") as cache_file:
        cache_file.write("{bad json")
    invalid, info = resolver.read_token_list_cache("ethereum")
    assert invalid is None and info["source"] == "invalid"
    with open(path, "w", encoding="utf-8") as cache_file:
        json.dump({"fetched_at": time.time(), "tokens": "not a list"}, cache_file)
    invalid, info = resolver.read_token_list_cache("ethereum")
    assert invalid is None and "tokens array" in info["error"]


@pytest.mark.parametrize(("candidate", "query", "quality"), [
    ("Example Token", "Example Token", "exact"),
    ("Example Token", "example token", "case_insensitive_exact"),
    ("Example-Token", "example token", "normalized_exact"),
    ("Example Token", "Example", "partial"),
    ("Example Token", "Unrelated", "different"),
    ("", "Example", "missing"),
])
def test_name_matching_explains_match_quality(candidate, query, quality):
    assert resolver.score_field(candidate, query)["quality"] == quality


def test_verified_code_beats_same_score_unverified_code(monkeypatch):
    tokens = [token("Example", "EX", ADDRESS_A), token("Example", "EX", ADDRESS_B)]
    monkeypatch.setattr(resolver, "fetch_coingecko_token_list", lambda *a, **kw: (tokens, {}))
    monkeypatch.setattr(resolver, "get_api_key", lambda _: "test-key")
    responses = []
    for value in ("0x", "0x6000"):
        response = MagicMock()
        response.json.return_value = {"result": value}
        responses.append(response)
    monkeypatch.setattr(resolver.requests, "get", MagicMock(side_effect=responses))

    result = resolver.resolve_contract_address("Example", "EX")

    assert [match["contract_address"] for match in result["matches"]] == [ADDRESS_B, ADDRESS_A]
    assert [match["etherscan_verification"] for match in result["matches"]] == ["verified", "not_contract"]
    assert result["status"] == "ambiguous"


def test_etherscan_limits_verification_requests(monkeypatch):
    tokens = [token("Example", "EX", "0x" + format(index, "040x")) for index in range(8)]
    monkeypatch.setattr(resolver, "fetch_coingecko_token_list", lambda *a, **kw: (tokens, {}))
    monkeypatch.setattr(resolver, "get_api_key", lambda _: "test-key")
    response = MagicMock()
    response.json.return_value = {"result": "0x6000"}
    get = MagicMock(return_value=response)
    monkeypatch.setattr(resolver.requests, "get", get)

    result = resolver.resolve_contract_address("Example", "EX")

    assert get.call_count == resolver.MAX_ETHERSCAN_VERIFICATIONS
    assert sum(match["etherscan_verification"] == "skipped_candidate_limit"
               for match in result["matches"]) == 3
