'''
This file is for the main cli of the program. 

Current cli implementation:
As according to sprint 1 w2; The cli lets users input address and from calls all the different fetchers and returns 1 json file containing all accepted results
'''
import json
import os
import re
from datetime import datetime, timezone

from agents.ba import describe_validation_error, ask_llm, is_exit_command, parse_ba_response, perform_next_action
from uuid import uuid4


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


def is_transaction_hash(value):
    """Recognize the 0x-prefixed 32-byte transaction hash format."""
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{64}", value))


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


def format_fetcher_result(data):
    passed = not (isinstance(data, dict) and "error" in data)
    return {
        "status": "pass" if passed else "fail",
        "data": data if passed else None,
        "error": None if passed else data.get("error"),
    }


def utc_now_iso():
    """Return a spec-friendly UTC timestamp."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )


def run_fetcher(name, module_name, function_name, *args, **kwargs):
    try:
        module = __import__(module_name, fromlist=[function_name])
        fetcher = getattr(module, function_name)
        data = fetcher(*args, **kwargs)
        return format_fetcher_result(data)
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

    if name == "tx_hash" and not address_analysis["is_transaction_hash"]:
        return "Transaction hash fetcher skipped because the input is not a transaction hash."

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


def fetch_results(address, requested_fields=None):
    """Run each address-based fetcher and keep failures isolated."""
    address_analysis = analyze_address_format(address)
    address_analysis["is_transaction_hash"] = is_transaction_hash(address)
    fetchers = [
        ("tx_hash", "fetchers.tx_hash_fetcher", "get_transaction_by_hash"),
        ("contract", "fetchers.contract_fetcher", "get_contract_info"),
        ("transactions", "fetchers.transaction_history_fetcher", "get_transactions"),
        ("honeypot", "scam_detectors.honeypot", "get_honeypot"),
        ("liquidity", "fetchers.liquidty_pairedPool_fetcher", "get_liquidity"),
        ("rugcheck", "scam_detectors.rugcheck", "get_rugcheck"),
        ("token_info", "fetchers.token_info_fetcher", "get_token_info"),
    ]
    results = {}

    field_fetchers = {
        "contract": "contract", "tx_history": "transactions",
        "tokens": "token_info", "liquidity": "liquidity",
    }
    selected = (
        {field_fetchers[field] for field in requested_fields}
        if requested_fields is not None else None
    )
    for name, module_name, function_name in fetchers:
        if selected is not None and name not in selected:
            continue
        # Explicit information requests do not need an extra contract lookup
        # merely to infer wallet/token type; the selected API can report failure.
        skip_reason = (
            None if selected is not None and name in {"token_info", "liquidity"}
            and address_analysis["chain_family"] == "evm"
            else should_skip_fetcher(name, address_analysis)
        )
        if skip_reason:
            results[name] = make_skip(skip_reason)
            continue

        if name in ("contract", "transactions", "token_info", "tx_hash"):
            results[name] = run_fetcher(
                name,
                module_name,
                function_name,
                address,
                chain_id=1,
            )
        else:
            results[name] = run_fetcher(name, module_name, function_name, address)

        if name == "contract":
            update_analysis_from_contract(address_analysis, results[name])

    return results, address_analysis


def _passed_data(results, name, default):
    result = results.get(name, {})
    if result.get("status") != "pass":
        return default
    data = result.get("data")
    return default if data is None else data


def normalize_contract_context(results):
    data = _passed_data(results, "contract", {})
    bytecode = data.get("bytecode")
    abi = data.get("abi")

    return {
        "is_contract": not is_empty_evm_bytecode(bytecode),
        "bytecode": bytecode,
        "abi": abi if isinstance(abi, list) else [],
        "verified_source": bool(abi),
        "creation_tx": data.get("creation_tx"),
        "creator": data.get("creator"),
    }


def normalize_tx_history_context(results):
    transactions = _passed_data(results, "transactions", [])
    if not isinstance(transactions, list):
        return []

    return [
        {
            "hash": tx.get("hash"),
            "from": tx.get("from"),
            "to": tx.get("to"),
            "value": str(tx.get("value_native", tx.get("value_wei", ""))),
            "timestamp": tx.get("timestamp"),
            "method": tx.get("function_name") or tx.get("method_id"),
        }
        for tx in transactions
        if isinstance(tx, dict)
    ]


def normalize_tokens_context(results):
    token_info = _passed_data(results, "token_info", {})
    token_transfers = token_info.get("token_transfers", [])
    if not isinstance(token_transfers, list):
        return []

    tokens_by_address = {}

    for transfer in token_transfers:
        if not isinstance(transfer, dict):
            continue

        contract_address = transfer.get("contractAddress")
        if not contract_address:
            continue

        token = tokens_by_address.setdefault(
            contract_address.lower(),
            {
                "symbol": transfer.get("tokenSymbol"),
                "contract_address": contract_address,
                "balance": None,
                "decimals": None,
            },
        )

        if token["symbol"] is None:
            token["symbol"] = transfer.get("tokenSymbol")

        if token["decimals"] is None:
            try:
                token["decimals"] = int(transfer.get("tokenDecimal"))
            except (TypeError, ValueError):
                token["decimals"] = None

    return list(tokens_by_address.values())


def normalize_liquidity_context(results):
    liquidity = _passed_data(results, "liquidity", [])
    if not isinstance(liquidity, list):
        return []

    return [
        {
            "pool_address": pool.get("pool_address"),
            "dex": pool.get("dex"),
            "token_pair": pool.get("token_pair") or [],
            "liquidity_usd": pool.get("liquidity_usd"),
            "liquidity_events": pool.get("liquidity_events") or [],
        }
        for pool in liquidity
        if isinstance(pool, dict)
    ]


def build_fetcher_provenance(results, fetched_at):
    fetcher_map = {
        "contract_fetcher": ("contract", ["contract"]),
        "tx_history_fetcher": ("transactions", ["tx_history"]),
        "token_fetcher": ("token_info", ["tokens"]),
        "liquidity_fetcher": ("liquidity", ["liquidity"]),
    }
    provenance = {}

    for fetcher_name, (result_key, fields) in fetcher_map.items():
        result = results.get(result_key, {})
        entry = {
            "fields": fields,
            "fetched_at": fetched_at,
            "status": result.get("status", "skip"),
        }

        if result.get("error"):
            entry["error"] = result["error"]

        provenance[fetcher_name] = entry

    return provenance


def build_address_context_json(address, results, address_analysis):
    """Build the SPEC.md AddressContext JSON structure from fetcher output."""
    queried_at = utc_now_iso()

    return {
        "chain": "ethereum" if address_analysis.get("chain_family") == "evm" else "unknown",
        "address": address,
        "queried_at": queried_at,
        "contract": normalize_contract_context(results),
        "tx_history": normalize_tx_history_context(results),
        "tokens": normalize_tokens_context(results),
        "liquidity": normalize_liquidity_context(results),
        "fetcher_provenance": build_fetcher_provenance(results, queried_at),
    }


def fetch_contract_address_results(token_name, token_symbol="", chain_id=1):
    """Run the token-name/symbol contract-address resolver."""
    token_name = (token_name or "").strip()
    token_symbol = (token_symbol or "").strip()

    if not token_name and not token_symbol:
        raise ValueError("A token name or symbol is required.")

    result = run_fetcher(
        "contract_address",
        "fetchers.contract_address_fetcher",
        "resolve_contract_address",
        token_name,
        token_symbol,
        chain_id=chain_id,
    )

    return {
        "query": {
            "token_name": token_name,
            "token_symbol": token_symbol,
            "chain_id": chain_id,
        },
        "results": {
            "contract_address": result,
        },
        "summary": {
            "passed": 1 if result["status"] == "pass" else 0,
            "failed": 1 if result["status"] == "fail" else 0,
            "skipped": 1 if result["status"] == "skip" else 0,
        },
    }


def save_info(address, results, address_analysis, output_file=None):
    """Save all fetcher results to the required combined JSON file."""
    output_file = output_file or JSON_FILE
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    info = build_address_context_json(address, results, address_analysis)

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(info, file, indent=4)


def save_contract_address_info(resolver_results, output_file=None):
    """Save contract-address resolver results to the combined JSON file."""
    output_file = output_file or JSON_FILE
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    info = {
        "lookup_type": "contract_address",
        **resolver_results,
    }

    with open(output_file, "w", encoding="utf-8") as file:
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


def resolve_ba_target(task, respond, output_file=None):
    """Run one known resolver; only continue with an unambiguous address."""
    raw_input = task.raw_input.value.strip()
    if task.raw_input.type == "token_name":
        resolver_results = fetch_contract_address_results(raw_input)
        result = resolver_results["results"]["contract_address"]
        save_contract_address_info(resolver_results, output_file=output_file)
        if result["status"] != "pass":
            respond(f"Contract address lookup failed: {result['error']}")
            return None
        data = result["data"]
        matches = data.get("matches", [])
        if not matches:
            respond("No matching Ethereum token contract was found. Please check the name or symbol.")
            return None
        lines = [f"Token resolver result: {data.get('status', 'unknown')}"]
        if data.get("cache", {}).get("warning"):
            lines.append(data["cache"]["warning"])
        for match in matches:
            lines.append(
                f"{match.get('name')} ({match.get('symbol')}): "
                f"{match.get('contract_address')} "
                f"[contract verification: {match.get('etherscan_verification', 'unknown')}]"
            )
        address = matches[0].get("contract_address")
        resolved = (
            data.get("status") == "resolved" and isinstance(address, str)
            and is_evm_address(address)
            and matches[0].get("etherscan_verification") != "not_contract"
        )
        if not resolved:
            lines.append("Please confirm the intended contract address from these candidates.")
        respond("\n".join(lines))
        # A resolver-only request is complete after displaying its result.
        return address if resolved and task.requested_fields else None

    if not is_transaction_hash(raw_input):
        respond("Please supply a complete Ethereum transaction hash.")
        return None
    result = run_fetcher(
        "tx_hash", "fetchers.tx_hash_fetcher", "get_transaction_by_hash",
        raw_input, chain_id=1,
    )
    if result["status"] != "pass":
        respond(f"Transaction lookup failed: {result['error']}")
        return None
    transaction = result["data"]
    addresses = []
    lines = [f"Transaction: {raw_input}"]
    for role in ("from", "to"):
        address = transaction.get(role)
        lines.append(f"{role}: {address or 'not supplied (may be contract creation)'}")
        if isinstance(address, str) and is_evm_address(address) and address not in addresses:
            addresses.append(address)
    if task.requested_fields and len(addresses) != 1:
        lines.append("Please supply the address you want information about from this transaction.")
    respond("\n".join(lines))
    return addresses[0] if task.requested_fields and len(addresses) == 1 else None


def handle_ba_request(prompt, history=None):
    """Classify once, then execute each independent task in order."""
    try:
        analysis = ask_llm(prompt, history)
        batch = parse_ba_response(analysis)
    except ValueError as error:
        print(f"\nThe BA returned an invalid task definition. {describe_validation_error(error)}")
        return
    print(f"\n{analysis}")
    multiple = len(batch.tasks) > 1
    request_id = uuid4().hex if multiple else None
    for index, task in enumerate(batch.tasks, start=1):
        label = f"Task {index}: {task.request_type}"
        if task.raw_input:
            label += f" - {task.raw_input.value}"
        if multiple:
            print(f"\n{label}")

        def respond(message):
            print(f"\nResponse:\n{message}")
            if history is not None:
                content = f"{label}\n{message}" if multiple else message
                history.append({"role": "assistant", "content": content})

        output_file = (
            os.path.join(os.path.dirname(JSON_FILE), "requests", request_id, f"task_{index}.json")
            if multiple else None
        )
        try:
            execute_ba_task(task, respond, output_file)
        except Exception as error:
            # A failed fetch/save for one task must not discard other answers.
            respond(f"This task could not be completed: {error}")


def execute_ba_task(task, respond, output_file=None):
    """Run one task; returning here does not stop other tasks in the prompt."""
    analysis = task.model_dump_json()
    action_response = perform_next_action(analysis)
    if action_response:
        respond(action_response)
        return

    if task.chain != "ethereum":
        respond("Address lookups currently support Ethereum only.")
        return
    raw_input_type = task.raw_input.type if task.raw_input else None
    raw_input = task.raw_input.value.strip() if task.raw_input else ""
    if not raw_input:
        respond("Please supply a blockchain address, token name/symbol, or transaction hash.")
        return

    if raw_input_type in {"token_name", "tx_hash"}:
        expected_resolver = {
            "token_name": "token_name_resolver_fetcher",
            "tx_hash": "tx_hash_resolver_fetcher",
        }[raw_input_type]
        if not task.needs_resolution or task.resolution_plan != [expected_resolver]:
            respond("The BA did not provide a matching resolution plan. Please try again.")
            return
        raw_input = resolve_ba_target(task, respond, output_file)
        if raw_input is None:
            return

    if not is_evm_address(raw_input):
        respond("Please supply a complete Ethereum address.")
        return
    if not task.requested_fields:
        respond("Which information would you like: contract, transactions, tokens, or liquidity?")
        return

    fetcher_results, address_analysis = fetch_results(raw_input, task.requested_fields)
    print(
        f"\nAddress type: {address_analysis['chain_family']} / "
        f"{address_analysis['address_type']}"
    )
    print_results(fetcher_results)
    if output_file is None:
        save_info(raw_input, fetcher_results, address_analysis)
    else:
        save_info(raw_input, fetcher_results, address_analysis, output_file=output_file)
    respond(f"Requested information saved to {output_file or JSON_FILE}")


def run_cli():
    history = []
    print_banner()
    print("ChainGuard is ready. Type 'goodbye' to exit.")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if is_exit_command(user_input):
            print("Goodbye!")
            break

        if user_input:
            handle_ba_request(user_input, history)


if __name__ == "__main__":
    run_cli()
