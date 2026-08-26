'''
This file is for the main cli of the program. 

Current cli implementation:
As according to sprint 1 w2; The cli lets users input address and from calls all the different fetchers and returns 1 json file containing all accepted results
'''
import json
import os


JSON_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fetchers",
    "json_files",
    "info.json",
)

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def is_solana_address(address):
    """Recognize the Base58 address format used by Solana tokens."""
    base58_characters = set(
        "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    )
    return (
        32 <= len(address) <= 44
        and all(character in base58_characters for character in address)
    )

def print_banner():
    banner = r"""
   _____ _           _        _____                     _
  / ____| |         (_)      / ____|                   | |
 | |    | |__   __ _ _ _ __ | |  __ _   _  __ _ _ __ __| |
 | |    | '_ \ / _` | | '_ \| | |_ | | | |/ _` | '__/ _` |
 | |____| | | | (_| | | | | | |__| | |_| | (_| | | | (_| |
  \_____|_| |_|\__,_|_|_| |_|\_____|\__,_|\__,_|_|  \__,_|

        Blockchain Security Assistant
"""
    print(banner)


def fetch_results(address):
    """Run each address-based fetcher and keep failures isolated."""
    fetchers = [
        ("contract", "fetchers.contract_fetcher", "get_contract_info"),
        ("transactions", "fetchers.transaction_history_fetcher", "get_transactions"),
        ("honeypot", "fetchers.honeypot", "get_honeypot"),
        ("liquidity", "fetchers.liquidty_pairedPool_fetcher", "get_liquidity"),
        ("rugcheck", "fetchers.rugcheck", "get_rugcheck"),
    ]
    results = {}

    for name, module_name, function_name in fetchers:
        if name == "rugcheck" and not is_solana_address(address):
            results[name] = {
                "status": "skip",
                "data": None,
                "error": "RugCheck supports Solana token addresses only.",
            }
            continue

        try:
            module = __import__(module_name, fromlist=[function_name])
            fetcher = getattr(module, function_name)

            if name == "contract":
                data = fetcher(address, chain_id=1)
            elif name == "transactions":
                data = fetcher(address, chain_id=1)
            else:
                data = fetcher(address)

            passed = not (isinstance(data, dict) and "error" in data)
            results[name] = {
                "status": "pass" if passed else "fail",
                "data": data if passed else None,
                "error": None if passed else data.get("error"),
            }
        except Exception as error:
            results[name] = {
                "status": "fail",
                "data": None,
                "error": str(error),
            }

    return results


def save_info(address, results):
    """Save all fetcher results to the required combined JSON file."""
    os.makedirs(os.path.dirname(JSON_FILE), exist_ok=True)
    info = {
        "address": address,
        "results": results,
        "summary": {
            "passed": sum(result["status"] == "pass" for result in results.values()),
            "failed": sum(result["status"] == "fail" for result in results.values()),
            "skipped": sum(result["status"] == "skip" for result in results.values()),
        },
    }

    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(info, file, indent=4)


def print_results(results):
    for name, result in results.items():
        status = result["status"].upper()
        color = {
            "pass": GREEN,
            "fail": RED,
            "skip": YELLOW,
        }[result["status"]]
        print(f"{color}{name}: {status}{RESET}")
        if result["error"]:
            print(f"  {result['error']}")


if __name__ == "__main__":
    print_banner()
    address = input("Wallet or token address: ").strip()

    if not address:
        raise SystemExit("An address is required.")

    fetcher_results = fetch_results(address)
    print_results(fetcher_results)
    save_info(address, fetcher_results)
    print(f"Combined results saved to {JSON_FILE}")

