"""Replace this stub with your detector implementation."""

try:
    from .schema import AddressContext, DetectionResult
except ImportError:
    from schema import AddressContext, DetectionResult


def detect(context: AddressContext) -> DetectionResult:
    """Return the shared contract; the CLI does not invoke this stub."""
    return DetectionResult(
        label="insufficient_evidence",
        risk_type="unknown",
        confidence=0.0,
        evidence=[{
            "description": "No detection algorithm has been implemented in this template.",
            "weight": 0.0,
        }],
    )
