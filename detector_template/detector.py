from schema import AddressContext, DetectionResult


def detect(context: AddressContext) -> DetectionResult:

    # DETECTION LOGIC GOES HERE
    # This is where users can implement their own detection logic based on the provided AddressContext.

    return DetectionResult(
        label="unknown",
        risk_type=None,
        confidence=0.0,
        evidence=[
            "No detection logic has been implemented yet."
        ]
    )