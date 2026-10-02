"""Shared configuration for an external detector endpoint."""

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


CONFIG_PATH = Path(os.environ.get(
    "CHAINGUARD_DETECTOR_CONFIG_PATH",
    Path(__file__).resolve().parents[1] / "detector_config.json",
))


class DetectorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    name: str = Field(default="ChainGuard External Detector", min_length=1, pattern=r"\S")
    endpoint: HttpUrl = "http://127.0.0.1:9000/detect"
    mode: Literal["template", "generic"] = "template"
    required_input_type: Literal[
        "address",
        "address_with_context",
    ] = "address_with_context"
    is_llm_based: bool = False


def default_detector_config() -> DetectorConfig:
    return DetectorConfig(
        enabled=os.environ.get("CHAINGUARD_DETECTOR_DEFAULT_ENABLED", "false").casefold() == "true",
        name=os.environ.get(
            "CHAINGUARD_DETECTOR_DEFAULT_NAME",
            "ChainGuard External Detector",
        ),
        endpoint=os.environ.get(
            "CHAINGUARD_DETECTOR_DEFAULT_ENDPOINT",
            "http://127.0.0.1:9000/detect",
        ),
    )


def get_detector_settings() -> DetectorConfig:
    """
    Return the saved detector settings.

    If detector_config.json does not exist yet, return the default settings.
    Unlike load_detector_config(), this still returns the configuration when
    the detector is disabled because the Settings page needs to edit it.
    """
    try:
        contents = CONFIG_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default_detector_config()
    except OSError as error:
        raise ValueError("Cannot read detector_config.json.") from error

    try:
        return DetectorConfig.model_validate(json.loads(contents))
    except (ValueError, json.JSONDecodeError) as error:
        raise ValueError(
            "Invalid detector_config.json."
        ) from error


def save_detector_settings(config: DetectorConfig) -> DetectorConfig:
    """
    Validate and save detector configuration to detector_config.json.
    """
    validated = DetectorConfig.model_validate(config)

    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(
                validated.model_dump(mode="json"),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise ValueError("Could not save detector settings.") from error

    return validated


def load_detector_config() -> DetectorConfig | None:
    """
    Return the configured detector only when it is enabled.

    The BA and scam-check pipeline use this function.
    Settings are read on every request, so saved changes apply without restart.
    """
    config = get_detector_settings()

    if not config.enabled:
        return None

    return config


def detector_metadata(config: DetectorConfig | None) -> dict:
    return {
        "selected_detector": config.name if config else None,
        "detector_configured": config is not None,
        "required_input_type": (
            config.required_input_type
            if config
            else "address_with_context"
        ),
    }