try:
    from .schema import AddressContext, DetectionResult
except ImportError:
    from schema import AddressContext, DetectionResult


def detect(context: AddressContext) -> DetectionResult:
    evidence = []

    if context.address_analysis:
        address_type = context.address_analysis.get("address_type", "unknown")
        evidence.append(f"Address analysis classified this as: {address_type}.")

    if context.contract:
        if context.contract.get("error"):
            evidence.append(f"Contract fetch returned an error: {context.contract['error']}")
        elif context.contract.get("bytecode"):
            evidence.append("Contract data was returned with bytecode.")
        else:
            evidence.append("Contract data was returned but no bytecode was found.")

    if context.honeypot:
        if context.honeypot.get("error"):
            evidence.append(f"Honeypot fetch returned an error: {context.honeypot['error']}")
        elif context.honeypot.get("is_honeypot") is True:
            evidence.append("Honeypot check flagged the address/token as suspicious.")

    if context.rugcheck:
        if context.rugcheck.get("error"):
            evidence.append(f"RugCheck fetch returned an error: {context.rugcheck['error']}")

    if context.tx_hash and context.tx_hash.get("hash"):
        evidence.append("Transaction hash payload was supplied and parsed.")

    if not evidence:
        evidence.append("No fetcher data was returned for this address.")

    label = "low_risk"
    risk_type = None
    confidence = 0.35

    if any("suspicious" in item.lower() for item in evidence):
        label = "medium_risk"
        risk_type = "manual_review"
        confidence = 0.72

    return DetectionResult(
        label=label,
        risk_type=risk_type,
        confidence=confidence,
        evidence=evidence[:5]
    )
