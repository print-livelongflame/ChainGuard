from pydantic import BaseModel, Field
from typing import Any


class FetcherResult(BaseModel):
    """Standard status envelope returned by the fetcher pipeline."""

    status: str
    data: Any = None
    error: str | None = None


class FetcherProvenance(BaseModel):
    """Metadata describing a fetcher used to build normalized context."""

    fields: list[str] = Field(default_factory=list)
    fetched_at: str | None = None
    status: str = "skip"
    error: str | None = None


class ContractAddressMatch(BaseModel):
    """A ranked token-name/symbol contract candidate."""

    name: str | None = None
    symbol: str | None = None
    contract_address: str
    match_score: float = Field(ge=0.0, le=1.0)
    match_quality: str
    match_reason: dict[str, Any] = Field(default_factory=dict)
    etherscan_verification: str = "pending"


class ContractAddressLookup(BaseModel):
    """Payload returned by the contract-address resolver fetcher."""

    token_list_length: int = Field(ge=0)
    status: str
    matches: list[ContractAddressMatch] = Field(default_factory=list)
    query: dict[str, Any] = Field(default_factory=dict)
    cache: dict[str, Any] = Field(default_factory=dict)


class ContractAddressResults(BaseModel):
    """Result envelope used by the contract-address lookup route."""

    query: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, FetcherResult] = Field(default_factory=dict)
    summary: dict[str, int] = Field(default_factory=dict)


class AddressContext(BaseModel):
    address: str
    chain: str = "unknown"
    queried_at: str | None = None
    address_analysis: dict[str, Any] = Field(default_factory=dict)

    contract: dict[str, Any] = Field(default_factory=dict)
    transactions: list[dict[str, Any]] = Field(default_factory=list)
    token: dict[str, Any] = Field(default_factory=dict)
    liquidity: dict[str, Any] | list[dict[str, Any]] = Field(default_factory=dict)
    honeypot: dict[str, Any] = Field(default_factory=dict)
    rugcheck: dict[str, Any] = Field(default_factory=dict)
    tx_hash: dict[str, Any] = Field(default_factory=dict)
    raw_results: dict[str, Any] = Field(default_factory=dict)

    # Normalized fields emitted by src.main.save_info().
    tx_history: list[dict[str, Any]] = Field(default_factory=list)
    tokens: list[dict[str, Any]] = Field(default_factory=list)
    fetcher_provenance: dict[str, FetcherProvenance] = Field(default_factory=dict)


class DetectionResult(BaseModel):
    label: str
    risk_type: str | None = None

    confidence: float = Field(
        ge=0.0,
        le=1.0
    )

    evidence: list[str] = Field(default_factory=list)