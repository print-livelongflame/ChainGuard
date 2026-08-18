'''
This file is just for calling the api and printing the json file 


Test address for honey pot: 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48

Test address for rug check: So11111111111111111111111111111111111111112

both need to take different addresses as input and return the json file for the respective api
meaning the user will input the address and the script will call both api's and return the json file for both api's


'''
import json
import requests

HONEYPOT_URL = "https://api.honeypot.is/v2/IsHoneypot"
RUGCHECK_URL = "https://api.rugcheck.xyz/v1/tokens/{}/report"


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


def main():
    token_address = input("Token address: ").strip()

    print("\n=== Honeypot ===")
    honeypot_data = get_honeypot(token_address)
    print(json.dumps(honeypot_data, indent=2))

    print("\n=== RugCheck ===")
    rugcheck_data = get_rugcheck(token_address)
    print(json.dumps(rugcheck_data, indent=2))


if __name__ == "__main__":
    main()