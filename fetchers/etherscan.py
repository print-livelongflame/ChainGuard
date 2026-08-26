import json
import os
import importlib
import sys
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")
TEST_JSON_FOLDER = os.path.join(BASE_DIR, "json_files_test")

ETHERSCAN_URL = "https://api.etherscan.io/v2/api"

try:
	ETHERSCAN_API_KEY = importlib.import_module(
		"api_keys.api_keys"
	).ETHERSCAN_API_KEY
except (ImportError, AttributeError):
	ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY", "")


def get_token_transfers(
	contract_address: str,
	address: str = "",
	chain_id: int = 1,
) -> dict:
	response = requests.get(
		ETHERSCAN_URL,
		params={
			"module": "account",
			"action": "tokentx",
			"contractaddress": contract_address,
			"chainid": chain_id,
			"apikey": ETHERSCAN_API_KEY,
		},
		timeout=10,
	)
	response.raise_for_status()
	return response.json()


def save_json(filename: str, data, folder=JSON_FOLDER):
	os.makedirs(folder, exist_ok=True)
	filepath = os.path.join(folder, filename)

	with open(filepath, "w", encoding="utf-8") as file:
		json.dump(data, file, indent=4)

	print(f"Saved {filename} to {filepath}")


if __name__ == "__main__" and "-test" in sys.argv:
	token_address = input("Token contract address: ").strip()
	if not token_address:
		raise SystemExit("A token contract address is required.")

	try:
		data = get_token_transfers(contract_address=token_address)
		save_json("token_transfers.json", data, TEST_JSON_FOLDER)
		print("TEST: PASS - JSON returned")
	except Exception as error:
		save_json("token_transfers.json", {"error": str(error)}, TEST_JSON_FOLDER)
		print(f"TEST: FAIL - {error}")