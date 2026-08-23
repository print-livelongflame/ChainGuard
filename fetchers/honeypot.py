"""
This file calls the Honeypot API and saves the result as JSON.

Test Address:
0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48

NOTE:
This API is for token investigation, not wallet investigation.
"""

import json
import os
import glob
import requests

HONEYPOT_URL = "https://api.honeypot.is/v2/IsHoneypot"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")


def clear_json_folder():
    os.makedirs(JSON_FOLDER, exist_ok=True)

    for file in glob.glob(os.path.join(JSON_FOLDER, "honeypot*.json")):
        os.remove(file)


def save_json(filename, data):
    filepath = os.path.join(JSON_FOLDER, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Saved: {filepath}")


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
    main()