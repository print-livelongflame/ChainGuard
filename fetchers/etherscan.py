import json
import os
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FOLDER = os.path.join(BASE_DIR, "json_files")

# Testing Address - 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48
# Etherscan API Key (made by nathaniel) - HJURHSSH7FZS5BN1VIB637N95326I7WTZ6


url = "https://api.etherscan.io/v2/api?module=account&action=tokentx&apikey=HJURHSSH7FZS5BN1VIB637N95326I7WTZ6&chainid=1&contractaddress=0xdAC17F958D2ee523a2206206994597C13D831ec7"

response = requests.get(url)

print(response.text)