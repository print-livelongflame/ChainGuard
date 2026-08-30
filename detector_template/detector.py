from schema import AddressContext, DetectionResult


def detect(context: AddressContext) -> DetectionResult:

    # --------------------------------------------------
    # YOUR DETECTION LOGIC GOES HERE
    # --------------------------------------------------

    return DetectionResult(
        label="unknown",
        risk_type=None,
        confidence=0.0,
        evidence=[
            "No detection logic has been implemented yet."
        ]
    )