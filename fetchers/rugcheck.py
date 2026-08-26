"""
This file calls the RugCheck API and saves the result as JSON.

Test Address:
So11111111111111111111111111111111111111112

NOTE:
This API is for token investigation, not wallet investigation.
"""

import json
import os
import glob
import sys
import requests

RUGCHECK_URL = "https://api.rugcheck.xyz/v1/tokens/{}/report"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")
TEST_JSON_FOLDER = os.path.join(BASE_DIR, "json_files_test")


def clear_json_folder():
    os.makedirs(JSON_FOLDER, exist_ok=True)

    for file in glob.glob(os.path.join(JSON_FOLDER, "rugcheck*.json")):
        os.remove(file)


def save_json(filename, data, folder=JSON_FOLDER):
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Saved: {filepath}")


def run_test():
    token_address = input("Solana token address: ").strip()
    if not token_address:
        raise SystemExit("A Solana token address is required.")

    data = get_rugcheck(token_address)
    save_json("rugcheck.json", data, TEST_JSON_FOLDER)
    if "error" in data:
        print(f"TEST: FAIL - {data['error']}")
    else:
        print("TEST: PASS - JSON returned")


def get_rugcheck(token_address):
    try:
        response = requests.get(
            RUGCHECK_URL.format(token_address),
            timeout=30,
        )

        response.raise_for_status()
        return response.json()

    except Exception as e:
        return {"error": str(e)}


def main():
    token_address = input("Token address: ").strip()

    clear_json_folder()

    data = get_rugcheck(token_address)

    if "error" not in data:
        save_json("rugcheck.json", data)
    else:
        print(data)


if __name__ == "__main__":
    if "-test" in sys.argv:
        run_test()
    else:
        main()