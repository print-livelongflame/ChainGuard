from pydantic import BaseModel, Field
from typing import Any


class AddressContext(BaseModel):
    address: str
    chain: str = "unknown"
    address_analysis: dict[str, Any] = Field(default_factory=dict)

    contract: dict[str, Any] = Field(default_factory=dict)
    transactions: list[dict[str, Any]] = Field(default_factory=list)
    token: dict[str, Any] = Field(default_factory=dict)
    liquidity: dict[str, Any] | list[dict[str, Any]] = Field(default_factory=dict)
    honeypot: dict[str, Any] = Field(default_factory=dict)
    rugcheck: dict[str, Any] = Field(default_factory=dict)
    tx_hash: dict[str, Any] = Field(default_factory=dict)
    raw_results: dict[str, Any] = Field(default_factory=dict)


class DetectionResult(BaseModel):
    label: str
    risk_type: str | None = None

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    evidence: list[str] = Field(default_factory=list)