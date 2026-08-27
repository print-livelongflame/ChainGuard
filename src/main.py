'''
This file is for the main cli of the program. 

Current cli implementation:
As according to sprint 1 w2; The cli lets users input address and from calls all the different fetchers and returns 1 json file containing all accepted results
'''
import json
import os
import re


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


def is_evm_address(address):
    """Recognize the 0x-prefixed 20-byte address format used by EVM chains."""
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", address))


def is_solana_address(address):
    """Recognize the Base58 address format used by Solana tokens."""
    base58_characters = set(
        "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    )
    return (
        32 <= len(address) <= 44
        and all(character in base58_characters for character in address)
    )


def is_empty_evm_bytecode(bytecode):
    """EOA wallets have no contract bytecode at their address."""
    return bytecode in (None, "", "0x")


def is_eip7702_delegation(bytecode):
    """EIP-7702 delegated EOAs store 0xef0100 followed by a 20-byte address."""
    return (
        isinstance(bytecode, str)
        and len(bytecode) == 48
        and bytecode.lower().startswith("0xef0100")
    )


def abi_has_erc20_shape(abi):
    """Use verified ABI function names as a best-effort ERC-20 token signal."""
    if not isinstance(abi, list):
        return False

    function_names = {
        item.get("name")
        for item in abi
        if isinstance(item, dict) and item.get("type") == "function"
    }
    required_names = {"totalSupply", "balanceOf", "transfer"}

    return required_names.issubset(function_names)


def analyze_address_format(address):
    """Classify the address format before any API-specific checks."""
    evm_format = is_evm_address(address)
    solana_format = is_solana_address(address)

    if evm_format:
        chain_family = "evm"
    elif solana_format:
        chain_family = "solana"
    else:
        chain_family = "unknown"

    return {
        "chain_family": chain_family,
        "address_type": "unknown",
        "checks": {
            "evm_format": evm_format,
            "solana_format": solana_format,
            "bytecode_present": None,
            "eip7702_delegation": None,
            "erc20_abi_shape": None,
        },
        "notes": [],
    }


def update_analysis_from_contract(address_analysis, contract_result):
    """Refine an EVM address classification with contract bytecode and ABI."""
    if address_analysis["chain_family"] != "evm":
        return

    if contract_result["status"] != "pass":
        address_analysis["notes"].append(
            "Could not check EVM bytecode because contract lookup failed."
        )
        return

    contract_data = contract_result["data"]
    bytecode = contract_data.get("bytecode")
    bytecode_present = not is_empty_evm_bytecode(bytecode)
    eip7702_delegation = is_eip7702_delegation(bytecode)
    erc20_abi_shape = abi_has_erc20_shape(contract_data.get("abi"))

    address_analysis["checks"]["bytecode_present"] = bytecode_present
    address_analysis["checks"]["eip7702_delegation"] = eip7702_delegation
    address_analysis["checks"]["erc20_abi_shape"] = erc20_abi_shape

    if not bytecode_present:
        address_analysis["address_type"] = "wallet"
        address_analysis["notes"].append(
            "No EVM bytecode found, so this looks like a wallet address."
        )
    elif eip7702_delegation:
        address_analysis["address_type"] = "delegated_wallet"
        address_analysis["notes"].append(
            "EIP-7702 delegation bytecode found, so this looks like a delegated EOA wallet."
        )
    elif erc20_abi_shape:
        address_analysis["address_type"] = "token_contract"
        address_analysis["notes"].append(
            "Verified ABI includes common ERC-20 functions."
        )
    else:
        address_analysis["address_type"] = "contract"
        address_analysis["notes"].append(
            "Bytecode found, but verified ABI did not confirm an ERC-20 token."
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


def make_skip(error):
    return {
        "status": "skip",
        "data": None,
        "error": error,
    }


def run_fetcher(name, module_name, function_name, address):
    try:
        module = __import__(module_name, fromlist=[function_name])
        fetcher = getattr(module, function_name)

        if name in ("contract", "transactions", "token_info"):
            data = fetcher(address, chain_id=1)
        else:
            data = fetcher(address)

        passed = not (isinstance(data, dict) and "error" in data)
        return {
            "status": "pass" if passed else "fail",
            "data": data if passed else None,
            "error": None if passed else data.get("error"),
        }
    except Exception as error:
        return {
            "status": "fail",
            "data": None,
            "error": str(error),
        }


def should_skip_fetcher(name, address_analysis):
    chain_family = address_analysis["chain_family"]
    address_type = address_analysis["address_type"]

    if name in ("contract", "transactions", "token_info") and chain_family != "evm":
        return "This fetcher supports EVM addresses only."

    if name == "token_info" and address_type not in ("wallet", "delegated_wallet"):
        return "Token info fetcher skipped because it expects an EVM wallet address."

    if name in ("honeypot", "liquidity"):
        if chain_family != "evm":
            return "This fetcher supports EVM token contracts only."

        if address_type == "wallet":
            return "Token-only fetcher skipped because this looks like a wallet."

        if address_type == "delegated_wallet":
            return (
                "Token-only fetcher skipped because this looks like an "
                "EIP-7702 delegated wallet."
            )

        if address_type != "token_contract":
            return (
                "Token-only fetcher skipped because this was not confirmed "
                "as an ERC-20 token."
            )

    if name == "rugcheck" and chain_family != "solana":
        return "RugCheck supports Solana token addresses only."

    return None


def fetch_results(address):
    """Run each address-based fetcher and keep failures isolated."""
    address_analysis = analyze_address_format(address)
    fetchers = [
        ("contract", "fetchers.contract_fetcher", "get_contract_info"),
        ("transactions", "fetchers.transaction_history_fetcher", "get_transactions"),
        ("honeypot", "scam_detectors.honeypot", "get_honeypot"),
        ("liquidity", "fetchers.liquidty_pairedPool_fetcher", "get_liquidity"),
        ("rugcheck", "scam_detectors.rugcheck", "get_rugcheck"),
        ("token_info", "fetchers.token_info_fetcher", "get_token_info"),
    ]
    results = {}

    for name, module_name, function_name in fetchers:
        skip_reason = should_skip_fetcher(name, address_analysis)
        if skip_reason:
            results[name] = make_skip(skip_reason)
            continue

        results[name] = run_fetcher(name, module_name, function_name, address)

        if name == "contract":
            update_analysis_from_contract(address_analysis, results[name])

    return results, address_analysis


def save_info(address, results, address_analysis):
    """Save all fetcher results to the required combined JSON file."""
    os.makedirs(os.path.dirname(JSON_FILE), exist_ok=True)
    info = {
        "address": address,
        "address_analysis": address_analysis,
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

    fetcher_results, address_analysis = fetch_results(address)
    print(f"Address type: {address_analysis['chain_family']} / {address_analysis['address_type']}")
    print_results(fetcher_results)
    save_info(address, fetcher_results, address_analysis)
    print(f"Combined results saved to {JSON_FILE}")
