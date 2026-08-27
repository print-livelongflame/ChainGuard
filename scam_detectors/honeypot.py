"""
This file calls the Honeypot API and saves the result as JSON.

NOTE:
This API is for token investigation, not wallet investigation.
"""

import json
import os
import glob
import sys
import requests

HONEYPOT_URL = "https://api.honeypot.is/v2/IsHoneypot"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")
TEST_JSON_FOLDER = os.path.join(BASE_DIR, "json_files_test")


def clear_json_folder():
    os.makedirs(JSON_FOLDER, exist_ok=True)

    for file in glob.glob(os.path.join(JSON_FOLDER, "honeypot*.json")):
        os.remove(file)


def save_json(filename, data, folder=JSON_FOLDER):
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Saved: {filepath}")


def run_test():
    token_address = input("Token address: ").strip()
    if not token_address:
        raise SystemExit("A token address is required.")

    data = get_honeypot(token_address)
    save_json("honeypot.json", data, TEST_JSON_FOLDER)
    if "error" in data:
        print(f"TEST: FAIL - {data['error']}")
    else:
        print("TEST: PASS - JSON returned")


def get_honeypot(token_address):
    try:
        response = requests.get(
            HONEYPOT_URL,
            params={"address": token_address},
            timeout=30,
        )

        response.raise_for_status()
        return response.json()

    except Exception as e:
        return {"error": str(e)}


def main():
    token_address = input("Token address: ").strip()

    clear_json_folder()

    data = get_honeypot(token_address)

    if "error" not in data:
        save_json("honeypot.json", data)
    else:
        print(data)


if __name__ == "__main__":
    if "-test" in sys.argv:
        run_test()
    else:
        main()