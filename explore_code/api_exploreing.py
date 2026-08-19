'''
This file is just for calling the api and printing the json file 


Test address for honey pot: 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48

Test address for rug check: So11111111111111111111111111111111111111112

both need to take different addresses as input and return the json file for the respective api
meaning the user will input the address and the script will call both api's and return the json file for both api's


NOTE: This code is for finding information on tokens not the wallet address. 


'''
import json
import os
import glob
import requests

HONEYPOT_URL = "https://api.honeypot.is/v2/IsHoneypot"
RUGCHECK_URL = "https://api.rugcheck.xyz/v1/tokens/{}/report"

JSON_FOLDER = "json_files"


def clear_json_folder():
    os.makedirs(JSON_FOLDER, exist_ok=True)

    for file in glob.glob(os.path.join(JSON_FOLDER, "*.json")):
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


def get_dexscreener(token_address):
    try:
        response = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{token_address}",
            timeout=30,
        )

        response.raise_for_status()
        return response.json()

    except Exception as e:
        return {"error": str(e)}


def main():
    token_address = input("Token address: ").strip()

    # Delete old JSON files
    clear_json_folder()

    print("\n=== Honeypot ===")
    honeypot_data = get_honeypot(token_address)

    if "error" not in honeypot_data:
        save_json("honeypot.json", honeypot_data)
    else:
        print(honeypot_data)

    print("\n=== RugCheck ===")
    rugcheck_data = get_rugcheck(token_address)

    if "error" not in rugcheck_data:
        save_json("rugcheck.json", rugcheck_data)
    else:
        print(rugcheck_data)

    print("\n=== DexScreener ===")
    dexscreener_data = get_dexscreener(token_address)

    if "error" not in dexscreener_data:
        save_json("dexscreener.json", dexscreener_data)
    else:
        print(dexscreener_data)


if __name__ == "__main__":
    main()