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
import sys

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


def resolve_contract_address(token_name: str, token_symbol: str, chain_id: int = 1) -> dict:
    """Resolve possible contract addresses from a token name/symbol."""
    token_name = (token_name or "").strip()
    token_symbol = (token_symbol or "").strip()

    if not token_name or not token_symbol:
        return {"error": "Token name and symbol are required."}

    # ---------------------------------------------------------
    # 1. Retrieve token list from chain using CoinGecko
    # ---------------------------------------------------------

    gecko_base_params = {
        "include_platform": "true"
    }

    response = requests.get(
        COINGECKO_URL,
        params=gecko_base_params,
        timeout=10
    )
    response.raise_for_status()

    gecko_token_list = response.json()
    platform_key = CHAIN_PLATFORM_KEYS.get(chain_id)

    if not platform_key:
        return {"error": f"Unsupported chain_id for contract-address resolver: {chain_id}"}

    # ---------------------------------------------------------
    # 2. Query list to find matches
    # ---------------------------------------------------------

    possible_matches = []

    for token in gecko_token_list:
        token_platforms = token.get("platforms") or {}
        contract_address = token_platforms.get(platform_key)

        name_matches = token.get("name", "").lower() == token_name.lower()
        symbol_matches = token.get("symbol", "").lower() == token_symbol.lower()

        if (name_matches or symbol_matches) and contract_address:
            possible_matches.append({
                "name": token.get("name"),
                "symbol": token.get("symbol"),
                "contract_address": contract_address,
                "match_reason": {
                    "name": name_matches,
                    "symbol": symbol_matches,
                },
                "etherscan_verification": "pending",
            })

    if len(possible_matches) == 0:
        result = "not_found"
    elif len(possible_matches) == 1:
        result = "resolved"
    else:
        result = "ambiguous"

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
        }

    etherscan_base_params = {
        "chainid": chain_id,
        "apikey": ETHERSCAN_API_KEY
    }

    for match in possible_matches:
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
