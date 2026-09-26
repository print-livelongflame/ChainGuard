"""
This fetcher retrieves some basic token info for ChainGuard.

Information retrieved:
- Token Balances
- Metadata

Uses:
- Etherscan API V2 (tokentx, token balance endpoints)

Etherscan API V2 uses one API key for supported EVM chains.
The chain is selected using the chainid parameter.

Chain IDs:
- Ethereum: 1
- BSC: 56

"""

import os
import sys
import json
import importlib
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

def get_token_info(wallet_address: str, chain_id: int = 1) -> dict:

    if not ETHERSCAN_API_KEY.strip():
        return {
            "error": (
                "Etherscan API key is missing. Add ETHERSCAN_API_KEY "
                "to api_keys/api_keys.py or set it as an environment variable."
            )
        }

    # Common parameters used by Etherscan V2
    base_params = {
        "chainid": chain_id,
        "apikey": ETHERSCAN_API_KEY
    }

    # ---------------------------------------------------------
    # 1. Get token balances 
    # ---------------------------------------------------------

    tokenbal_params = {
        **base_params,
        "module": "account",
        "action": "tokentx",
        "address": wallet_address,
        "startblock": "0",
        "endblock": "99999999",
        "sort": "desc"
    }

    response = requests.get(
        ETHERSCAN_URL,
        params=tokenbal_params,
        timeout=10
    )

    response.raise_for_status()

    token_transfer_data = response.json()
    api_key_error = get_etherscan_api_key_error(token_transfer_data)
    if api_key_error:
        return {"error": api_key_error}

    token_transfers = token_transfer_data.get("result", [])

    # ---------------------------------------------------------
    # Return ChainGuard-friendly JSON
    # ---------------------------------------------------------
    return {
        "wallet_address": wallet_address,
        "chain_id": chain_id,
        "token_transfer_count": len(token_transfers),
        "token_transfers": token_transfers,
    }

def save_json(filename: str, data, folder=JSON_FOLDER):
    os.makedirs(folder, exist_ok=True)

    filepath = os.path.join(folder, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"Saved {filename} to {filepath}")

def run_test():
    address = input("Wallet address: ").strip()
    if not address:
        raise SystemExit("A wallet address is required.")

    try:
        data = get_token_info(wallet_address=address, chain_id=1)
        save_json("tokeninfo.json", data, TEST_JSON_FOLDER)
        print("TEST: PASS - JSON returned")
    except Exception as error:
        save_json("tokeninfo.json", {"error": str(error)}, TEST_JSON_FOLDER)
        print(f"TEST: FAIL - {error}")


if __name__ == "__main__":
    if "-test" in sys.argv:
        run_test()
    else:
        address = input("Wallet address: ").strip()
        if not address:
            raise SystemExit("A wallet address is required.")

        data = get_token_info(wallet_address=address, chain_id=1)
        save_json("tokeninfo.json", data)
        print(f"Saved token information to {JSON_FOLDER}")
