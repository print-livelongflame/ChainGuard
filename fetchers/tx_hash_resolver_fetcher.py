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
import requests
from api_keys.api_keys import ETHERSCAN_API_KEY
ETHERSCAN_URL = "https://api.etherscan.io/v2/api"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")
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

def save_json(filename: str, data):
    os.makedirs(JSON_FOLDER, exist_ok=True)
    filepath = os.path.join(JSON_FOLDER, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"Saved {filename} to {filepath}")

# Testing the function
tx_hash = "0x0d4890ecEc59cd55D640d36f7acc6"
data = get_transaction_by_hash(tx_hash)
save_json("transaction_data.json", data)
