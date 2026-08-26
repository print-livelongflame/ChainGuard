'''
This file is the tx-hash resolver fetcher. It is tx hash look up the transaction and extract address(es) involved 

For this we will use Etherscan API as well (gettransaction by hash)

test address: need hash
'''

#! ERROR: etherscan tx gettxinfo is not valid for v2 api action. 
#todo: need to check if etherscan has a valid endpoint for tx hash lookup and find a vaild testing input 

import os
import sys
import json
import importlib
import requests

try:
    ETHERSCAN_API_KEY = importlib.import_module(
        "api_keys.api_keys"
    ).ETHERSCAN_API_KEY
except (ImportError, AttributeError):
    ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY", "")
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")
TEST_JSON_FOLDER = os.path.join(BASE_DIR, "json_files_test")
#allow imports from project root
sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

def get_transaction_by_hash(
    tx_hash: str,
    chain_id: int = 1
) -> dict:
    params = {
        "chainid": chain_id,
        "module": "transaction",
        "action": "gettxinfo",
        "txhash": tx_hash,
        "apikey": ETHERSCAN_API_KEY
    }

    response = requests.get(ETHERSCAN_URL, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()
    return data.get("result", {})

def save_json(filename: str, data, folder=JSON_FOLDER):
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"Saved {filename} to {filepath}")


def run_test():
    tx_hash = input("Transaction hash: ").strip()
    if not tx_hash:
        raise SystemExit("A transaction hash is required.")

    try:
        data = get_transaction_by_hash(tx_hash)
        save_json("transaction_data.json", data, TEST_JSON_FOLDER)
        print("TEST: PASS - JSON returned")
    except Exception as error:
        save_json("transaction_data.json", {"error": str(error)}, TEST_JSON_FOLDER)
        print(f"TEST: FAIL - {error}")

if __name__ == "__main__":
    if "-test" in sys.argv:
        run_test()
    else:
        tx_hash = input("Transaction hash: ").strip()
        if not tx_hash:
            raise SystemExit("A transaction hash is required.")

        data = get_transaction_by_hash(tx_hash)
        save_json("transaction_data.json", data)
