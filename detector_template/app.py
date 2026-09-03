import os
import sys

from fastapi import FastAPI
from pydantic import BaseModel, Field

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from .schema import AddressContext, DetectionResult
    from .detector import detect
except ImportError:
    from schema import AddressContext, DetectionResult
    from detector import detect
from src.context_builder import build_address_context
from src.main import fetch_contract_address_results


app = FastAPI(
    title="ChainGuard Detector API",
    description="API wrapper for ChainGuard scam detectors",
    version="1.0.0"
)


class AnalyseRequest(BaseModel):
    address: str = Field(..., min_length=1)


class ContractAddressRequest(BaseModel):
    token_name: str = Field(..., min_length=1)
    token_symbol: str = Field(..., min_length=1)
    chain_id: int = 1


class AnalyseResponse(BaseModel):
    context: AddressContext
    detection_result: DetectionResult


@app.get("/")
def root():
    return {
        "name": "ChainGuard Detector API",
        "status": "running"
    }


@app.post("/detect", response_model=DetectionResult)
def run_detection(context: AddressContext):
    result = detect(context)
    return result


@app.post("/analyse", response_model=AnalyseResponse)
def run_analysis(request: AnalyseRequest):
    context = build_address_context(request.address)
    detection_result = detect(context)

    return {
        "context": context,
        "detection_result": detection_result
    }


@app.post("/resolve-contract-address")
def resolve_contract_address(request: ContractAddressRequest):
    return fetch_contract_address_results(
        request.token_name,
        request.token_symbol,
        chain_id=request.chain_id,
    )
