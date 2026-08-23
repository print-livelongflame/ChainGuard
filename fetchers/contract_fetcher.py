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

Test address:
0x0d4890ecEc59cd55D640d36f7acc6F7F512Fdb6e
"""

import os
import sys
import json
import requests


# Allow imports from project root
sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

from api_keys.api_keys import ETHERSCAN_API_KEY


# Etherscan API V2
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")


def get_contract_info(
    contract_address: str,
    chain_id: int = 1
) -> dict:

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


def save_json(filename: str, data):
    os.makedirs(JSON_FOLDER, exist_ok=True)

    filepath = os.path.join(JSON_FOLDER, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"Saved {filename} to {filepath}")


# ---------------------------------------------------------
# Testing
# ---------------------------------------------------------

address = "0x0d4890ecEc59cd55D640d36f7acc6F7F512Fdb6e"

data = get_contract_info(
    contract_address=address,
    chain_id=1
)

save_json("contract.json", data)

print(f"Saved contract information to {JSON_FOLDER}")