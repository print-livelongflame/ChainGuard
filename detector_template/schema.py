from pydantic import BaseModel, Field
from typing import Any


class AddressContext(BaseModel):
    address: str
    chain: str

    contract: dict[str, Any] = Field(default_factory=dict)
    transactions: list[dict[str, Any]] = Field(default_factory=list)
    token: dict[str, Any] = Field(default_factory=dict)
    liquidity: dict[str, Any] = Field(default_factory=dict)


class DetectionResult(BaseModel):
    label: str
    risk_type: str | None = None

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    evidence: list[str] = Field(default_factory=list)