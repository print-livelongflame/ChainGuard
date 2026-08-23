import json
import os

import requests

DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/{token_address}"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")


def get_liquidity(token_address: str) -> list[dict]:
    url = DEXSCREENER_URL.format(token_address=token_address)

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    data = response.json()

    liquidity = []

    for pair in data.get("pairs", []):
        liquidity.append({
            "pool_address": pair.get("pairAddress"),
            "dex": pair.get("dexId"),
            "token_pair": [
                pair.get("baseToken", {}).get("symbol"),
                pair.get("quoteToken", {}).get("symbol"),
            ],
            "liquidity_usd": pair.get("liquidity", {}).get("usd"),
        })

    return liquidity


def save_json(filename: str, data):
    os.makedirs(JSON_FOLDER, exist_ok=True)
    filepath = os.path.join(JSON_FOLDER, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"Saved {filename} to {filepath}")


# Testing the function
address = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"

data = get_liquidity(address)

save_json("liquidity.json", data)

print(f"Saved {len(data)} liquidity pools to {os.path.join(JSON_FOLDER, 'liquidity.json')}")