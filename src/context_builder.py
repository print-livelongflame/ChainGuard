import os
import sys

# Ensure the project root is importable so the builder can reuse the existing
# fetcher pipeline and schema without requiring a custom packaging setup.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from detector_template.schema import AddressContext
from src.main import fetch_results, build_address_context_json


def build_address_context(address: str) -> AddressContext:
    """Use the same four fetchers and normalized contract as the CLI."""
    address = (address or "").strip()
    if not address:
        raise ValueError("Address is required.")
    results, address_analysis = fetch_results(
        address, ["contract", "tx_history", "tokens", "liquidity"]
    )
    return AddressContext.model_validate(
        build_address_context_json(address, results, address_analysis)
    )
