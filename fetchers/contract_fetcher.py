"""
This fetcher retrieves contract information for ChainGuard.

Information retrieved:
- Contract bytecode
- ABI (if the contract is verified)
- Contract creator
- Contract creation transaction

Uses:
- Etherscan API V2

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


def get_contract_info(
    contract_address: str,
    chain_id: int = 1
) -> dict:

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
    # 1. Get bytecode
    # ---------------------------------------------------------

    bytecode_params = {
        **base_params,
        "module": "proxy",
        "action": "eth_getCode",
        "address": contract_address,
        "tag": "latest"
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
        return {"error": api_key_error}

    bytecode = bytecode_data.get("result")


    # ---------------------------------------------------------
    # 2. Get ABI
    # ---------------------------------------------------------

    abi_params = {
        **base_params,
        "module": "contract",
        "action": "getabi",
        "address": contract_address
    }

    response = requests.get(
        ETHERSCAN_URL,
        params=abi_params,
        timeout=10
    )

    response.raise_for_status()

    abi_data = response.json()
    api_key_error = get_etherscan_api_key_error(abi_data)
    if api_key_error:
        return {"error": api_key_error}

    abi = None

    # ABI is only available if the contract is verified
    if abi_data.get("status") == "1":
        try:
            abi = json.loads(abi_data.get("result"))
        except (TypeError, json.JSONDecodeError):
            abi = None


    # ---------------------------------------------------------
    # 3. Get creator and creation transaction
    # ---------------------------------------------------------

    creation_params = {
        **base_params,
        "module": "contract",
        "action": "getcontractcreation",
        "contractaddresses": contract_address
    }

    response = requests.get(
        ETHERSCAN_URL,
        params=creation_params,
        timeout=10
    )

    response.raise_for_status()

    creation_data = response.json()
    api_key_error = get_etherscan_api_key_error(creation_data)
    if api_key_error:
        return {"error": api_key_error}

    creator = None
    creation_tx = None

    if creation_data.get("status") == "1":

        result = creation_data.get("result", [])

        if result:
            contract_data = result[0]

            creator = contract_data.get("contractCreator")
            creation_tx = contract_data.get("txHash")


    # ---------------------------------------------------------
    # Return ChainGuard-friendly JSON
    # ---------------------------------------------------------

    return {
        "contract_address": contract_address,
        "chain_id": chain_id,
        "bytecode": bytecode,
        "abi": abi,
        "creator": creator,
        "creation_tx": creation_tx
    }


def save_json(filename: str, data, folder=JSON_FOLDER):
    os.makedirs(folder, exist_ok=True)

    filepath = os.path.join(folder, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"Saved {filename} to {filepath}")


def run_test():
    address = input("Contract address: ").strip()
    if not address:
        raise SystemExit("A contract address is required.")

    try:
        data = get_contract_info(contract_address=address, chain_id=1)
        save_json("contract.json", data, TEST_JSON_FOLDER)
        print("TEST: PASS - JSON returned")
    except Exception as error:
        save_json("contract.json", {"error": str(error)}, TEST_JSON_FOLDER)
        print(f"TEST: FAIL - {error}")


if __name__ == "__main__":
    if "-test" in sys.argv:
        run_test()
    else:
        address = input("Contract address: ").strip()
        if not address:
            raise SystemExit("A contract address is required.")

        data = get_contract_info(contract_address=address, chain_id=1)
        save_json("contract.json", data)
        print(f"Saved contract information to {JSON_FOLDER}")
