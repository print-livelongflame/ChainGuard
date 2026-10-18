"""Run ChainGuard's 20-case scam assessment evaluation.

From backend/: python -m evaluation.run_scam_eval          (preview only)
               python -m evaluation.run_scam_eval --run   (20 model assessments)
"""

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from agents.sch import ask_scam_checker
from src.llm_config import get_llm_settings
from src.llm_provider import provider_available, use_llm_settings
from src.main import CONTEXT_FIELDS, build_address_context_json, fetch_results
from src.schema import AddressContext


HERE = Path(__file__).resolve().parent
DATASET = HERE / "scam_cases.csv"
RESULTS = HERE / "results"
VALID_LABELS = {"scam", "not_scam"}


def load_cases():
    with DATASET.open(newline="", encoding="utf-8") as stream:
        cases = list(csv.DictReader(stream))
    if len(cases) != 20:
        raise ValueError(f"Expected exactly 20 evaluation cases; found {len(cases)}.")
    ids, addresses = set(), set()
    for case in cases:
        if case["expected_label"] not in VALID_LABELS:
            raise ValueError(f"Unsupported expected label in {case['case_id']}.")
        if not case["address"].startswith("0x") or len(case["address"]) != 42:
            raise ValueError(f"Invalid EVM address in {case['case_id']}.")
        if case["case_id"] in ids or case["address"].lower() in addresses:
            raise ValueError("Dataset case IDs and addresses must be unique.")
        if not case["source"].startswith("https://"):
            raise ValueError(f"Missing source URL for {case['case_id']}.")
        ids.add(case["case_id"])
        addresses.add(case["address"].lower())
    counts = Counter(case["expected_label"] for case in cases)
    if counts != {"scam": 10, "not_scam": 10}:
        raise ValueError(f"Expected 10 cases per label; found {dict(counts)}.")
    return cases


def run_case(case):
    address = case["address"]
    fetched, analysis = fetch_results(address, CONTEXT_FIELDS)
    context = AddressContext.model_validate(
        build_address_context_json(address, fetched, analysis)
    )
    result = ask_scam_checker(context)
    return {
        "case_id": case["case_id"],
        "address": address,
        "expected_label": case["expected_label"],
        "predicted_label": result.label,
        "correct": result.label == case["expected_label"],
        "confidence": result.confidence,
        "risk_type": result.risk_type,
        "evidence": [item.model_dump() for item in result.evidence],
        "explanation": result.explanation,
        "source": case["source"],
        "label_basis": case["label_basis"],
        "fetcher_provenance": {
            name: {"status": value.status, "error": value.error, "cache": value.cache}
            for name, value in context.fetcher_provenance.items()
        },
    }


def summarize(rows):
    total = len(rows)
    correct = sum(row["correct"] for row in rows)
    labels = ("scam", "not_scam", "insufficient_evidence")
    return {
        "total": total,
        "correct": correct,
        "exact_agreement": correct / total if total else 0.0,
        "predictions": dict(Counter(row["predicted_label"] for row in rows)),
        "by_expected_label": {
            label: {
                "total": sum(row["expected_label"] == label for row in rows),
                "correct": sum(row["expected_label"] == row["predicted_label"] == label for row in rows),
            }
            for label in sorted(VALID_LABELS)
        },
        "confusion_matrix": {
            expected: {
                predicted: sum(
                    row["expected_label"] == expected and row["predicted_label"] == predicted
                    for row in rows
                )
                for predicted in labels
            }
            for expected in sorted(VALID_LABELS)
        },
    }


def write_report(path, rows, *, started_at, status):
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": started_at,
        "status": status,
        "dataset": DATASET.name,
        "label_note": "not_scam entries are weak negatives: CRPWarner marks none of its listed rug-pull patterns; this is not proof of safety.",
        "summary": summarize(rows),
        "cases": rows,
    }
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Fetch evidence and make 20 Scam Checker calls.")
    args = parser.parse_args()
    cases = load_cases()
    print(f"Dataset validated: {len(cases)} cases (10 scam, 10 weak-negative not_scam).")
    print("Each --run assessment calls the configured Scam Checker once; blockchain evidence is fetched or read from cache.")
    if not args.run:
        print("Preview only. Add --run to make the 20 assessments.")
        return

    settings = get_llm_settings()
    provider = settings.assignments.scam_checker
    if provider == "local":
        available = settings.local.enabled and settings.local_verified
    else:
        available = provider_available(provider)
    if not available:
        raise SystemExit(
            f"The configured Scam Checker provider ({provider}) has no usable credentials or verified local connection. "
            "Configure it in admin settings before running assessments."
        )

    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    started_at = datetime.now(timezone.utc).isoformat()
    output = RESULTS / f"scam-evaluation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    with use_llm_settings(settings):
        for index, case in enumerate(cases, start=1):
            print(f"[{index}/20] Assessing {case['case_id']} ({case['address']})...", flush=True)
            try:
                rows.append(run_case(case))
            except Exception as error:
                rows.append({
                    "case_id": case["case_id"], "address": case["address"],
                    "expected_label": case["expected_label"], "predicted_label": "error",
                    "correct": False, "error": f"{type(error).__name__}: {error}",
                    "source": case["source"], "label_basis": case["label_basis"],
                })
            write_report(output, rows, started_at=started_at,
                         status="completed" if index == len(cases) else "in_progress")
    report = json.loads(output.read_text(encoding="utf-8"))
    print(json.dumps(report["summary"], indent=2))
    print(f"Detailed results saved to: {output}")


if __name__ == "__main__":
    main()
