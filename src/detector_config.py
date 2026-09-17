"""Shared, explicit registration of an external detector endpoint."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl, Field


CONFIG_PATH = Path(__file__).resolve().parents[1] / "detector_config.json"


class DetectorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    name: str = Field(min_length=1, pattern=r"\S")
    endpoint: HttpUrl
    mode: Literal["template", "generic"] = "template"
    required_input_type: Literal["address", "address_with_context"] = "address_with_context"
    is_llm_based: bool = False


def load_detector_config() -> DetectorConfig | None:
    """Missing registration means the bundled example is not a custom detector.

    Configuration records setup, not endpoint health or detector correctness.
    Read on each request so changes take effect during an existing CLI session.
    """
    try:
        contents = CONFIG_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ValueError("Cannot read detector_config.json.") from error
    try:
        config = DetectorConfig.model_validate(json.loads(contents))
    except ValueError as error:
        raise ValueError(
            "Invalid detector_config.json: expected enabled (boolean), name "
            "(non-empty string), and endpoint (HTTP/HTTPS URL)."
        ) from error
    return config if config.enabled else None


def detector_metadata(config: DetectorConfig | None) -> dict:
    return {
        "selected_detector": config.name if config else None,
        "detector_configured": config is not None,
        "required_input_type": config.required_input_type if config else "address_with_context",
    }
