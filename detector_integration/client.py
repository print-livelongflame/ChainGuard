import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.detector_config import load_detector_config
from src.schema import AddressContext, DetectionResult


def call_detector(context: AddressContext) -> DetectionResult:
    """Send a validated context to the configured detector service."""
    config = load_detector_config()
    if config is None:
        raise ValueError("No external detector is configured.")

    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("DETECTOR_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    request = Request(
        str(config.endpoint),
        data=context.model_dump_json().encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise ValueError(f"External detector returned HTTP {error.code}.") from error
    except URLError as error:
        raise ValueError("External detector could not be reached.") from error
    except json.JSONDecodeError as error:
        raise ValueError("External detector returned invalid JSON.") from error

    try:
        return DetectionResult.model_validate(payload)
    except ValueError as error:
        raise ValueError("External detector returned an invalid result.") from error