"""
Given a token name/symbol, resolve possible contract addresses.

This is a best-effort contract-address resolver. It should flag ambiguous
matches instead of pretending that a token name always maps to one address.

Uses:
- CoinGecko API token list
- Etherscan API V2
"""

import importlib
import json
import os
import re
import sys
import time
from difflib import SequenceMatcher

import requests


# Allow imports from project root
sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

try:
    ETHERSCAN_API_KEY = importlib.import_module(
        "api_keys.api_keys"
    ).ETHERSCAN_API_KEY
except (ImportError, AttributeError):
    ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY", "")


# Etherscan API V2
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/list"
CHAIN_PLATFORM_KEYS = {
    1: "ethereum",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")
TEST_JSON_FOLDER = os.path.join(BASE_DIR, "json_files_test")
CACHE_FOLDER = os.path.join(BASE_DIR, "cache")
CACHE_TTL_SECONDS = 6 * 60 * 60
MIN_FIELD_MATCH_SCORE = 0.65
MIN_SYMBOL_MATCH_SCORE = 0.8
MAX_MATCHES_RETURNED = 25
MAX_ETHERSCAN_VERIFICATIONS = 5


def normalize_text(value: str) -> str:
    """Normalize text for forgiving token name/symbol comparisons."""
    value = (value or "").strip().casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def compact_text(value: str) -> str:
    """Normalize text and remove separators for ticker-style comparisons."""
    return normalize_text(value).replace(" ", "")


def should_fuzzy_compare(candidate_value: str, query_value: str) -> bool:
    """Avoid expensive fuzzy checks for clearly unrelated values."""
    candidate_compact = compact_text(candidate_value)
    query_compact = compact_text(query_value)

    if not candidate_compact or not query_compact:
        return False

    if candidate_compact == query_compact:
        return True

    if query_compact in candidate_compact or candidate_compact in query_compact:
        return True

    short_length = min(len(candidate_compact), len(query_compact))
    if short_length <= 4:
        return False

    return (
        candidate_compact[0] == query_compact[0]
        and abs(len(candidate_compact) - len(query_compact)) <= 4
    )


def score_field(
    candidate_value: str,
    query_value: str,
    minimum_score: float = MIN_FIELD_MATCH_SCORE,
) -> dict:
    """Return a ranked comparison for one token field."""
    candidate_raw = (candidate_value or "").strip()
    query_raw = (query_value or "").strip()

    if not candidate_raw or not query_raw:
        return {
            "matches": False,
            "score": 0.0,
            "quality": "missing",
        }

    candidate_norm = normalize_text(candidate_raw)
    query_norm = normalize_text(query_raw)
    candidate_compact = compact_text(candidate_raw)
    query_compact = compact_text(query_raw)

    if candidate_raw == query_raw:
        quality = "exact"
        score = 1.0
    elif candidate_raw.casefold() == query_raw.casefold():
        quality = "case_insensitive_exact"
        score = 0.96
    elif candidate_norm == query_norm or candidate_compact == query_compact:
        quality = "normalized_exact"
        score = 0.9
    elif not should_fuzzy_compare(candidate_raw, query_raw):
        quality = "different"
        score = 0.0
    else:
        ratio = SequenceMatcher(None, candidate_norm, query_norm).ratio()
        compact_ratio = SequenceMatcher(None, candidate_compact, query_compact).ratio()
        best_ratio = max(ratio, compact_ratio)

        if (
            query_compact
            and candidate_compact
            and (
                query_compact in candidate_compact
                or candidate_compact in query_compact
            )
        ):
            quality = "partial"
            score = max(0.72, min(0.86, best_ratio))
        elif best_ratio >= minimum_score:
            quality = "fuzzy"
            score = best_ratio
        else:
            quality = "different"
            score = best_ratio

    return {
        "matches": score >= minimum_score,
        "score": round(score, 3),
        "quality": quality,
    }


def classify_match(name_match: dict, symbol_match: dict) -> str:
    """Create a readable quality label for a candidate match."""
    name_quality = name_match["quality"]
    symbol_quality = symbol_match["quality"]

    if name_quality == "exact" and symbol_quality == "exact":
        return "exact_name_and_symbol"
    if (
        name_quality in ("exact", "case_insensitive_exact")
        and symbol_quality in ("exact", "case_insensitive_exact")
    ):
        return "case_insensitive_name_and_symbol"
    if name_match["score"] >= 0.9 and symbol_match["score"] >= 0.9:
        return "normalized_name_and_symbol"
    if symbol_match["score"] >= 0.9 and name_match["score"] < MIN_FIELD_MATCH_SCORE:
        return "symbol_only"
    if name_match["score"] >= 0.9 and symbol_match["score"] < MIN_SYMBOL_MATCH_SCORE:
        return "name_only"
    if name_match["score"] >= MIN_FIELD_MATCH_SCORE and symbol_match["score"] >= MIN_SYMBOL_MATCH_SCORE:
        return "partial_name_and_symbol"
    if symbol_match["score"] >= MIN_SYMBOL_MATCH_SCORE:
        return "partial_symbol"
    if name_match["score"] >= MIN_FIELD_MATCH_SCORE:
        return "partial_name"

    return "weak"


def build_ranked_match(token: dict, contract_address: str, token_name: str, token_symbol: str) -> dict | None:
    """Build a scored resolver candidate, or None if it is too weak."""
    # A single query may be either a display name or ticker; compare both
    # without guessing the missing name/symbol from LLM memory.
    single_query = not token_name or not token_symbol
    name_query = token_name or token_symbol
    symbol_query = token_symbol or token_name
    name_match = score_field(token.get("name", ""), name_query)
    symbol_match = score_field(
        token.get("symbol", ""),
        symbol_query,
        minimum_score=MIN_SYMBOL_MATCH_SCORE,
    )

    if not name_match["matches"] and not symbol_match["matches"]:
        return None

    # Preserve combined-query ranking; a single query uses its best field.
    weighted_score = (
        max(name_match["score"], symbol_match["score"]) if single_query else
        (symbol_match["score"] * 0.55) + (name_match["score"] * 0.45)
    )

    return {
        "name": token.get("name"),
        "symbol": token.get("symbol"),
        "contract_address": contract_address,
        "match_score": round(weighted_score, 3),
        "match_quality": classify_match(name_match, symbol_match),
        "match_reason": {
            "name": name_match,
            "symbol": symbol_match,
        },
        "etherscan_verification": "pending",
    }


def get_resolution_status(matches: list[dict]) -> str:
    """Resolve the overall status without pretending close calls are certain."""
    if not matches:
        return "not_found"
    if len(matches) == 1:
        return "resolved" if matches[0]["match_score"] >= 0.9 else "possible_match"

    best_score = matches[0]["match_score"]
    second_score = matches[1]["match_score"]

    if best_score >= 0.95 and best_score - second_score >= 0.12:
        return "resolved"
    return "ambiguous"


def prepare_ranked_matches(matches: list[dict]) -> list[dict]:
    """Return a bounded, best-first candidate list."""
    matches.sort(
        key=lambda match: match["match_score"],
        reverse=True,
    )
    return matches[:MAX_MATCHES_RETURNED]


def get_cache_path(platform_key: str) -> str:
    """Return the on-disk cache path for a token platform."""
    return os.path.join(CACHE_FOLDER, f"coingecko_tokens_{platform_key}.json")


def read_token_list_cache(platform_key: str) -> tuple[list[dict] | None, dict]:
    """Read cached CoinGecko tokens and return token data plus cache details."""
    cache_path = get_cache_path(platform_key)

    if not os.path.exists(cache_path):
        return None, {
            "source": "missing",
            "path": cache_path,
            "age_seconds": None,
            "ttl_seconds": CACHE_TTL_SECONDS,
            "is_fresh": False,
        }

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as error:
        return None, {
            "source": "invalid",
            "path": cache_path,
            "age_seconds": None,
            "ttl_seconds": CACHE_TTL_SECONDS,
            "is_fresh": False,
            "error": str(error),
        }

    fetched_at = float(payload.get("fetched_at", 0))
    age_seconds = max(0, int(time.time() - fetched_at))
    tokens = payload.get("tokens")

    if not isinstance(tokens, list):
        return None, {
            "source": "invalid",
            "path": cache_path,
            "age_seconds": age_seconds,
            "ttl_seconds": CACHE_TTL_SECONDS,
            "is_fresh": False,
            "error": "Cached token list is missing a tokens array.",
        }

    return tokens, {
        "source": "cache",
        "path": cache_path,
        "age_seconds": age_seconds,
        "ttl_seconds": CACHE_TTL_SECONDS,
        "is_fresh": age_seconds <= CACHE_TTL_SECONDS,
    }


def write_token_list_cache(platform_key: str, tokens: list[dict]) -> dict:
    """Persist a refreshed CoinGecko token list."""
    os.makedirs(CACHE_FOLDER, exist_ok=True)
    cache_path = get_cache_path(platform_key)
    payload = {
        "fetched_at": time.time(),
        "platform": platform_key,
        "tokens": tokens,
    }

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    return {
        "source": "network",
        "path": cache_path,
        "age_seconds": 0,
        "ttl_seconds": CACHE_TTL_SECONDS,
        "is_fresh": True,
    }


def fetch_coingecko_token_list(platform_key: str, force_refresh: bool = False) -> tuple[list[dict], dict]:
    """Fetch CoinGecko tokens, using a short-lived local cache when possible."""
    cached_tokens, cache_info = read_token_list_cache(platform_key)

    if cached_tokens is not None and cache_info["is_fresh"] and not force_refresh:
        return cached_tokens, cache_info

    gecko_base_params = {
        "include_platform": "true"
    }

    try:
        response = requests.get(
            COINGECKO_URL,
            params=gecko_base_params,
            timeout=10
        )
        response.raise_for_status()
        tokens = response.json()
    except requests.RequestException as error:
        if cached_tokens is not None:
            cache_info["source"] = "stale_cache"
            cache_info["is_fresh"] = False
            cache_info["warning"] = (
                "CoinGecko refresh failed; using stale cached token list."
            )
            cache_info["refresh_error"] = str(error)
            return cached_tokens, cache_info

        raise

    if not isinstance(tokens, list):
        raise ValueError("CoinGecko token list response was not a list.")

    return tokens, write_token_list_cache(platform_key, tokens)


def get_etherscan_api_key_error(data: dict) -> str | None:
    """Return an API-key error message if Etherscan reports one."""
    message = str(data.get("message", ""))
    result = str(data.get("result", ""))

    if "Missing/Invalid API Key" in message or "Missing/Invalid API Key" in result:
        return (
            "Etherscan API key is missing or invalid. Add ETHERSCAN_API_KEY "
            "to api_keys/api_keys.py or set it as an environment variable."
        )

    return None


def resolve_contract_address(
    token_name: str,
    token_symbol: str = "",
    chain_id: int = 1,
    force_refresh: bool = False,
) -> dict:
    """Resolve possible contract addresses from a token name/symbol."""
    token_name = (token_name or "").strip()
    token_symbol = (token_symbol or "").strip()

    if not token_name and not token_symbol:
        return {"error": "A token name or symbol is required."}

    platform_key = CHAIN_PLATFORM_KEYS.get(chain_id)

    if not platform_key:
        return {"error": f"Unsupported chain_id for contract-address resolver: {chain_id}"}

    # ---------------------------------------------------------
    # 1. Retrieve token list from CoinGecko or local cache
    # ---------------------------------------------------------

    gecko_token_list, cache_info = fetch_coingecko_token_list(
        platform_key,
        force_refresh=force_refresh,
    )

    # ---------------------------------------------------------
    # 2. Query list to find and rank possible matches
    # ---------------------------------------------------------

    possible_matches = []

    for token in gecko_token_list:
        token_platforms = token.get("platforms") or {}
        contract_address = token_platforms.get(platform_key)

        if not contract_address:
            continue

        match = build_ranked_match(
            token,
            contract_address,
            token_name,
            token_symbol,
        )

        if match:
            possible_matches.append(match)

    possible_matches = prepare_ranked_matches(possible_matches)

    result = get_resolution_status(possible_matches)

    # ---------------------------------------------------------
    # 3. Use Etherscan to verify that matches have bytecode
    # ---------------------------------------------------------
    if not ETHERSCAN_API_KEY.strip():
        for match in possible_matches:
            match["etherscan_verification"] = "skipped_missing_api_key"

        return {
            "token_list_length": len(gecko_token_list),
            "status": result,
            "matches": possible_matches,
            "query": {
                "token_name": token_name,
                "token_symbol": token_symbol,
                "chain_id": chain_id,
                "platform": platform_key,
            },
            "cache": cache_info,
        }

    etherscan_base_params = {
        "chainid": chain_id,
        "apikey": ETHERSCAN_API_KEY
    }

    matches_to_verify = possible_matches[:MAX_ETHERSCAN_VERIFICATIONS]
    matches_skipped = possible_matches[MAX_ETHERSCAN_VERIFICATIONS:]

    for match in matches_skipped:
        match["etherscan_verification"] = "skipped_candidate_limit"

    for match in matches_to_verify:
        bytecode_params = {
            **etherscan_base_params,
            "module": "proxy",
            "action": "eth_getCode",
            "address": match["contract_address"],
            "tag": "latest",
        }

        response = requests.get(
            ETHERSCAN_URL,
            params=bytecode_params,
            timeout=10
        )

        response.raise_for_status()
        bytecode_data = response.json()
        api_key_error = get_etherscan_api_key_error(bytecode_data)

        if api_key_error:
            match["etherscan_verification"] = "failed"
            match["verification_error"] = api_key_error
            continue

        bytecode = bytecode_data.get("result")
        if bytecode in (None, "", "0x"):
            match["etherscan_verification"] = "not_contract"
        else:
            match["etherscan_verification"] = "verified"

    possible_matches.sort(
        key=lambda match: (
            match["etherscan_verification"] == "verified",
            match["match_score"],
        ),
        reverse=True,
    )

    result = get_resolution_status(possible_matches)

    # ---------------------------------------------------------
    # Return ChainGuard-friendly JSON
    # ---------------------------------------------------------
    return {
        "token_list_length": len(gecko_token_list),
        "status": result,
        "matches": possible_matches,
        "query": {
            "token_name": token_name,
            "token_symbol": token_symbol,
            "chain_id": chain_id,
            "platform": platform_key,
        },
        "cache": cache_info,
    }


def save_json(filename: str, data, folder=JSON_FOLDER):
    os.makedirs(folder, exist_ok=True)

    filepath = os.path.join(folder, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"Saved {filename} to {filepath}")


def run_test():
    token_name = input("Token name: ").strip()
    token_symbol = input("Token symbol: ").strip()
    if not token_name or not token_symbol:
        raise SystemExit("A token name and symbol are required.")

    try:
        data = resolve_contract_address(token_name, token_symbol, chain_id=1)
        save_json("contractAddressGuess.json", data, TEST_JSON_FOLDER)
        print("TEST: PASS - JSON returned")
    except Exception as error:
        save_json("contractAddressGuess.json", {"error": str(error)}, TEST_JSON_FOLDER)
        print(f"TEST: FAIL - {error}")


if __name__ == "__main__":
    if "-test" in sys.argv:
        run_test()
    else:
        token_name = input("Token name: ").strip()
        token_symbol = input("Token symbol: ").strip()
        if not token_name or not token_symbol:
            raise SystemExit("A token name and symbol are required.")

        data = resolve_contract_address(token_name, token_symbol, chain_id=1)
        save_json("contractAddressGuess.json", data)
        print(f"Saved contract address candidates to {JSON_FOLDER}")
