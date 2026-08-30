from fastapi import FastAPI
from schema import AddressContext, DetectionResult
from detector import detect


app = FastAPI(
    title="ChainGuard Detector API",
    description="API wrapper for ChainGuard scam detectors",
    version="1.0.0"
)


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