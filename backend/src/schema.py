from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FetcherResult(BaseModel):
    status: str
    data: Any = None
    error: str | None = None


class FetcherProvenance(BaseModel):
    fields: list[str] = Field(default_factory=list)
    fetched_at: str | None = None
    status: str = "skip"
    error: str | None = None


class ContractAddressMatch(BaseModel):
    name: str | None = None
    symbol: str | None = None
    contract_address: str
    match_score: float = Field(ge=0.0, le=1.0)
    match_quality: str
    match_reason: dict[str, Any] = Field(default_factory=dict)
    etherscan_verification: str = "pending"


class ContractAddressLookup(BaseModel):
    token_list_length: int = Field(ge=0)
    status: str
    matches: list[ContractAddressMatch] = Field(default_factory=list)
    query: dict[str, Any] = Field(default_factory=dict)
    cache: dict[str, Any] = Field(default_factory=dict)


class ContractAddressResults(BaseModel):
    query: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, FetcherResult] = Field(default_factory=dict)
    summary: dict[str, int] = Field(default_factory=dict)


class AddressContext(BaseModel):
    address: str
    chain: str = "unknown"
    queried_at: str | None = None
    address_analysis: dict[str, Any] = Field(default_factory=dict)
    contract: dict[str, Any] = Field(default_factory=dict)
    liquidity: list[dict[str, Any]] = Field(default_factory=list)
    tx_history: list[dict[str, Any]] = Field(default_factory=list)
    tokens: list[dict[str, Any]] = Field(default_factory=list)
    fetcher_provenance: dict[str, FetcherProvenance] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    description: str = Field(min_length=1)
    weight: float = Field(ge=0.0, le=1.0)


class DetectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    label: Literal["scam", "not_scam", "insufficient_evidence"]
    risk_type: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceItem]
    explanation: str | None = None