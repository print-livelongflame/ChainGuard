import json
import os
import sys

import requests

DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/{token_address}"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")
TEST_JSON_FOLDER = os.path.join(BASE_DIR, "json_files_test")


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


def save_json(filename: str, data, folder=JSON_FOLDER):
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"Saved {filename} to {filepath}")


def run_test():
    address = input("Token address: ").strip()
    if not address:
        raise SystemExit("A token address is required.")

    try:
        data = get_liquidity(address)
        save_json("liquidity.json", data, TEST_JSON_FOLDER)
        print("TEST: PASS - JSON returned")
    except Exception as error:
        save_json("liquidity.json", {"error": str(error)}, TEST_JSON_FOLDER)
        print(f"TEST: FAIL - {error}")


if __name__ == "__main__":
    if "-test" in sys.argv:
        run_test()
    else:
        address = input("Token address: ").strip()
        if not address:
            raise SystemExit("A token address is required.")

        data = get_liquidity(address)
        save_json("liquidity.json", data)
        print(f"Saved {len(data)} liquidity pools to {os.path.join(JSON_FOLDER, 'liquidity.json')}")