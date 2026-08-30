import os
import sys

# Ensure the project root is importable so the builder can reuse the existing
# fetcher pipeline and schema without requiring a custom packaging setup.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from detector_template.schema import AddressContext
from src.main import fetch_results


def _safe_result_data(result):
    """Return only the successful payload data from a fetcher result.

    The CLI stores fetcher results in a status/data/error structure, so the
    detector should receive clean dictionaries/lists rather than the wrapper
    metadata itself.
    """
    if not isinstance(result, dict):
        return {}
    return result.get("data") if result.get("status") == "pass" else {}


def build_address_context(address: str) -> AddressContext:
    """Build a detector-friendly AddressContext from the existing fetchers.

    This is the important bridge between the raw blockchain fetchers and the
    future detector logic. Instead of having the detector understand each fetcher
    result individually, we normalise everything into one AddressContext object
    that contains the address analysis, contract data, transaction history, token
    information, liquidity data, and any detector-specific outputs.
    """
    address = (address or "").strip()

    if not address:
        raise ValueError("Address is required.")

    # Reuse the exact existing CLI fetch pipeline instead of re-implementing it.
    # This keeps the API and CLI consistent while still allowing the API to work
    # in memory without needing to save info.json.
    results, address_analysis = fetch_results(address)

    return AddressContext(
        address=address,
        chain="ethereum" if address_analysis.get("chain_family") == "evm" else "unknown",
        address_analysis=address_analysis,
        contract=_safe_result_data(results.get("contract")),
        transactions=_safe_result_data(results.get("transactions")) or [],
        token=_safe_result_data(results.get("token_info")) or {},
        liquidity=_safe_result_data(results.get("liquidity")) or {},
        honeypot=_safe_result_data(results.get("honeypot")) or {},
        rugcheck=_safe_result_data(results.get("rugcheck")) or {},
        tx_hash=_safe_result_data(results.get("tx_hash")) or {},
        raw_results=results,
    )
