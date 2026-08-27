"""
This file is the tx-hash resolver fetcher.

Given a transaction hash, look up the transaction
and extract the addresses involved.

Uses:
- Etherscan API V2

Example transaction hash:

0xbc78ab8a9e9a0bca7d0321a27b2c03addeae08ba81ea98b03cd3dd237eabed44
"""

import os
import sys
import json
import importlib
import requests

# =========================
# API KEY LOADING
# =========================

try:
    ETHERSCAN_API_KEY = importlib.import_module(
        "api_keys.api_keys"
    ).ETHERSCAN_API_KEY

except (ImportError, AttributeError):
    ETHERSCAN_API_KEY = os.environ.get(
        "ETHERSCAN_API_KEY",
        ""
    )

ETHERSCAN_URL = "https://api.etherscan.io/v2/api"

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

JSON_FOLDER = os.path.join(
    BASE_DIR,
    "json_files"
)

TEST_JSON_FOLDER = os.path.join(
    BASE_DIR,
    "json_files_test"
)

# allow imports from project root
sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


# =========================
# ETHERSCAN LOOKUP
# =========================

def get_transaction_by_hash(
    tx_hash: str,
    chain_id: int = 1
) -> dict:

    params = {
        "chainid": chain_id,
        "module": "proxy",
        "action": "eth_getTransactionByHash",
        "txhash": tx_hash,
        "apikey": ETHERSCAN_API_KEY
    }

    response = requests.get(
        ETHERSCAN_URL,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    result = data.get("result")

    if result is None:
        raise Exception(
            f"No transaction found for hash: {tx_hash}"
        )

    return result


# =========================
# ADDRESS EXTRACTION
# =========================

def extract_addresses(
    tx_data: dict
) -> dict:

    return {
        "transaction_hash": tx_data.get("hash"),
        "from": tx_data.get("from"),
        "to": tx_data.get("to"),
    }


# =========================
# JSON SAVER
# =========================

def save_json(
    filename: str,
    data,
    folder=JSON_FOLDER
):

    os.makedirs(
        folder,
        exist_ok=True
    )

    filepath = os.path.join(
        folder,
        filename
    )

    with open(
        filepath,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4
        )

    print(
        f"Saved {filename} to {filepath}"
    )


# =========================
# TEST MODE
# =========================

def run_test():

    tx_hash = input(
        "Transaction hash: "
    ).strip()

    if not tx_hash:
        raise SystemExit(
            "A transaction hash is required."
        )

    try:

        tx_data = get_transaction_by_hash(
            tx_hash
        )

        extracted = extract_addresses(
            tx_data
        )

        save_json(
            "transaction_data.json",
            tx_data,
            TEST_JSON_FOLDER
        )

        save_json(
            "transaction_addresses.json",
            extracted,
            TEST_JSON_FOLDER
        )

        print(
            "TEST: PASS - transaction found"
        )

    except Exception as error:

        save_json(
            "transaction_error.json",
            {
                "error": str(error)
            },
            TEST_JSON_FOLDER
        )

        print(
            f"TEST: FAIL - {error}"
        )


if __name__ == "__main__":

    if "-test" in sys.argv:

        run_test()

    else:

        tx_hash = input(
            "Transaction hash: "
        ).strip()

        if not tx_hash:
            raise SystemExit(
                "A transaction hash is required."
            )

        tx_data = get_transaction_by_hash(
            tx_hash
        )

        extracted = extract_addresses(
            tx_data
        )

        save_json(
            "transaction_data.json",
            tx_data
        )

        save_json(
            "transaction_addresses.json",
            extracted
        )

        print(
            json.dumps(
                extracted,
                indent=4
            )
        )