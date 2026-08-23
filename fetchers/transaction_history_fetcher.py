'''
This file is to get the recetn transaction history of a given wallet address. 

For this we will use Etherscan API as well

Information retrieved:
- Recent transactions
- Incoming transactions
- Outgoing transactions
- Transaction hash
- From / To addresses
- Value
- Timestamp
- Block number
- Gas information
- Transaction status

Test address:
0x0d4890ecEc59cd55D640d36f7acc6F7F512Fdb6e
'''
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


ETHERSCAN_URL = "https://api.etherscan.io/v2/api"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")


def get_transactions(
    address: str,
    chain_id: int = 1,
    start_block: int = 0,
    end_block: int = 99999999,
    page: int = 1,
    offset: int = 100,
    sort: str = "desc"
) -> list[dict]:

    params = {
        "chainid": chain_id,
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": start_block,
        "endblock": end_block,
        "page": page,
        "offset": offset,
        "sort": sort,
        "apikey": ETHERSCAN_API_KEY
    }

    response = requests.get(
        ETHERSCAN_URL,
        params=params,
        timeout=10
    )

    response.raise_for_status()

    data = response.json()

    # Etherscan returns status 0 when there are no transactions
    if data.get("status") != "1":
        message = data.get("message", "")

        if "No transactions found" in str(message):
            return []

        return []

    transactions = []

    for tx in data.get("result", []):

        value_wei = int(tx.get("value", 0))

        # Convert Wei to native coin
        value_native = value_wei / 10**18

        transactions.append({
            "hash": tx.get("hash"),
            "block_number": tx.get("blockNumber"),
            "timestamp": tx.get("timeStamp"),

            "from": tx.get("from"),
            "to": tx.get("to"),

            "direction": (
                "incoming"
                if tx.get("to", "").lower() == address.lower()
                else "outgoing"
            ),

            "value_wei": value_wei,
            "value_native": value_native,

            "gas": tx.get("gas"),
            "gas_used": tx.get("gasUsed"),
            "gas_price": tx.get("gasPrice"),

            "nonce": tx.get("nonce"),

            "transaction_index": tx.get(
                "transactionIndex"
            ),

            "is_error": tx.get("isError"),
            "error_code": tx.get("txreceipt_status"),

            "method_id": tx.get("methodId"),
            "function_name": tx.get("functionName")
        })

    return transactions


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

transactions = get_transactions(
    address=address,
    chain_id=1,
    offset=100
)

save_json(
    "transactions.json",
    transactions
)

print(
    f"Saved {len(transactions)} transactions "
    f"to {os.path.join(JSON_FOLDER, 'transactions.json')}"
)