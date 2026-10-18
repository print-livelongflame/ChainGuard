"""Run with python -m evaluation.run --output evaluation/results/run-name."""
import argparse
import csv
import hashlib
import json
import random
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agents import ba, fi, sch
from evaluation.cases import CASES
from src import llm_provider
from src.llm_config import get_llm_settings
from src.prompt_strategies import apply_strategy
from src.schema import AddressContext, DetectionResult

STRATEGIES = ("zero_shot", "chain_of_thought", "few_shot")


def score(case, output):
    """Objective task checks only. Explanation quality requires blind human review."""
    if case["agent"] == "scam_checker":
        result = sch.parse_scam_checker_response(output)
        checks = {"label": result.label == case["label"]}
        if "risk_type" in case:
            checks["risk_type"] = result.risk_type == case["risk_type"]
        checks["trace_null"] = result.reasoning_trace is None
        return checks, result.label
    if case["agent"] == "business_analyser":
        tasks = ba.parse_ba_response(output).tasks
        expected = case["expected"]
        checks = {"single_task": len(tasks) == 1}
        task = tasks[0]
        for field in ("in_scope", "request_type", "requested_fields"):
            if field in expected:
                actual = getattr(task, field)
                checks[field] = sorted(actual) == sorted(expected[field]) if isinstance(actual, list) else actual == expected[field]
        if "raw_type" in expected:
            checks["raw_type"] = task.raw_input is not None and task.raw_input.type == expected["raw_type"]
        if expected.get("clarify"):
            checks["clarify"] = bool(task.message and task.message.strip()) and not task.requested_fields
        return checks, str((task.in_scope, task.request_type, task.raw_input.type if task.raw_input else None, sorted(task.requested_fields)))
    if not output.strip():
        raise ValueError("Empty explanation")
    return {}, None  # No keyword proxy for detector faithfulness.


def write_reports(directory, rows, manifest):
    groups = defaultdict(list)
    for row in rows:
        groups[row["agent"], row["strategy"]].append(row)
    summary = []
    for (agent, strategy), trials in sorted(groups.items()):
        scored = [r for r in trials if r["agent"] != "forensic_investigator"]
        signatures = defaultdict(list)
        for row in trials:
            signatures[row["case_id"]].append(row.get("signature"))
        repeatable = [len(set(values)) == 1 and None not in values for values in signatures.values() if len(values) > 1]
        summary.append({"agent": agent, "strategy": strategy, "trials": len(trials),
            "valid_output_rate": sum(r["valid"] for r in trials) / len(trials),
            "objective_pass_rate": sum(r["valid"] and all(r["checks"].values()) for r in scored) / len(scored) if scored else None,
            "same_decision_rate": statistics.mean(repeatable) if repeatable and agent != "forensic_investigator" else None,
            "mean_seconds": statistics.mean(r["seconds"] for r in trials),
            "reported_total_tokens": sum(r["usage"]["total_tokens"] for r in trials if r.get("usage")),
            "usage_available_trials": sum(r.get("usage") is not None for r in trials)})
    if summary:
        with (directory / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
            writer.writeheader(); writer.writerows(summary)
    blind = rows.copy()
    random.Random(manifest["seed"] + 1).shuffle(blind)
    with (directory / "blind-review.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["review_id", "case_id", "rubric", "answer", "factual_support_0_2", "task_fidelity_0_2", "uncertainty_0_2", "clarity_0_2", "notes"]
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        key = []
        for index, row in enumerate(blind):
            review_id = f"R{index + 1:04}"
            case = next(c for c in CASES if c["id"] == row["case_id"])
            writer.writerow({"review_id": review_id, "case_id": case["id"], "rubric": case["rubric"], "answer": row.get("output", "[request failed]")})
            key.append({"review_id": review_id, "strategy": row["strategy"], "repeat": row["repeat"], "case_id": row["case_id"]})
    (directory / "review-key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    planned = manifest.get("planned_trials", "not recorded")
    lines = ["# Prompt strategy evaluation", "", f"Provider: {manifest['provider']}; model: {manifest['model']}; temperature: {manifest['temperature']}; repeats: {manifest['repeats']}.",
        "", f"Completed trials: {len(rows)} / {planned}. Failed trials: {sum(not r['valid'] for r in rows)}.",
        "", "Synthetic, author-labelled cases. No real-world detection accuracy claim. Objective scores exclude explanation quality; FI requires human review. Errors count as failed trials. Repeats of a case are not independent cases.", "",
        "| Agent | Strategy | Valid | Objective pass | Same decision | Mean seconds |", "|---|---|---:|---:|---:|---:|"]
    def percent(value):
        return "n/a" if value is None else f"{value:.1%}"
    for item in summary:
        lines.append(f"| {item['agent']} | {item['strategy']} | {percent(item['valid_output_rate'])} | {percent(item['objective_pass_rate'])} | {percent(item['same_decision_rate'])} | {item['mean_seconds']:.2f} |")
    lines += ["", "Review blind-review.csv before opening review-key.json. Score each dimension 0 (fails), 1 (partial), 2 (fully meets rubric). Do not infer a winner from latency or JSON validity alone. No significance test or universal superiority claim is provided."]
    lines += ["", "## Objective failures", ""]
    failures = [row for row in rows if not row["valid"] or (row["checks"] and not all(row["checks"].values()))]
    if not failures:
        lines.append("None observed among the completed objective checks.")
    for row in failures:
        failed = ", ".join(name for name, passed in row["checks"].items() if not passed) or row.get("error_type", "unknown")
        lines.append(f"- {row['case_id']}, {row['strategy']}, repeat {row['repeat'] + 1}: {failed}.")
    (directory / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20261018)
    parser.add_argument("--agents", nargs="+", choices=list({c["agent"] for c in CASES}), default=["scam_checker", "business_analyser", "forensic_investigator"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1 or not 0 <= args.temperature <= 1:
        parser.error("repeats must be positive; temperature must be 0–1")
    settings = get_llm_settings().model_copy(deep=True)
    provider = settings.assignments.scam_checker
    cases = [c for c in CASES if c["agent"] in args.agents]
    jobs = [(case, strategy, repeat) for repeat in range(args.repeats) for case in cases for strategy in STRATEGIES]
    random.Random(args.seed).shuffle(jobs)
    print(f"{len(jobs)} requests; provider={provider}; temperature={args.temperature}; repeats={args.repeats}", flush=True)
    if args.dry_run:
        return
    args.output.mkdir(parents=True, exist_ok=False)
    model = settings.local.model if provider == "local" else llm_provider._PROVIDERS[provider]["model"]
    manifest = {"started_utc": datetime.now(timezone.utc).isoformat(), "provider": provider, "model": model,
        "temperature": args.temperature, "repeats": args.repeats, "seed": args.seed,
        "cases_sha256": hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
        "prompt_sha256": hashlib.sha256((ba.SYSTEM_PROMPT + sch.SYSTEM_PROMPT + fi.SYSTEM_PROMPT + json.dumps({a: [apply_strategy([], a, s) for s in STRATEGIES] for a in args.agents}, sort_keys=True)).encode()).hexdigest(),
        "budgets": llm_provider.OUTPUT_TOKEN_BUDGETS, "agents": args.agents, "planned_trials": len(jobs)}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (args.output / "cases.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    llm_provider.set_progress_enabled(False)
    rows = []
    for index, (case, strategy, repeat) in enumerate(jobs):
        agent = case["agent"]
        setattr(settings.assignments, agent, provider)
        tuning = getattr(settings.agents, agent)
        tuning.prompt_strategy, tuning.temperature = strategy, args.temperature
        row = {"case_id": case["id"], "agent": agent, "strategy": strategy, "repeat": repeat, "valid": False, "checks": {}}
        def capture(*positional, **kwargs):
            messages = kwargs.get("messages", positional[0] if positional else [])
            row["messages"] = apply_strategy(messages, agent, strategy)
            row["response_format"] = kwargs.get("response_format")
            row["max_tokens"] = kwargs.get("max_tokens", 8192)
            text, usage = llm_provider.complete_with_usage(*positional, **kwargs)
            row["output"], row["usage"] = text, usage
            return text
        started = time.perf_counter()
        try:
            with llm_provider.use_llm_settings(settings), patch.object({"scam_checker": sch, "business_analyser": ba, "forensic_investigator": fi}[agent], "complete", capture):
                if agent == "scam_checker":
                    sch.ask_scam_checker(AddressContext.model_validate(case["context"]))
                elif agent == "business_analyser":
                    with patch.object(ba, "load_detector_config", return_value=None):
                        ba.ask_llm(case["prompt"])
                else:
                    with patch.object(fi, "load_detector_config", return_value=SimpleNamespace(name="Benchmark detector", is_llm_based=False)):
                        fi.explain_detector_result(DetectionResult.model_validate(case["result"]))
            row["checks"], row["signature"] = score(case, row["output"])
            row["valid"] = True
        except Exception as error:
            # Provider exceptions can include request headers; keep only their type.
            row["error_type"] = type(error).__name__
        row["seconds"] = round(time.perf_counter() - started, 4)
        rows.append(row)
        with (args.output / "trials.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
        write_reports(args.output, rows, manifest)
        print(f"{index+1}/{len(jobs)} {case['id']} {strategy}: {'valid' if row['valid'] else row['error_type']}", flush=True)
        if len(rows) >= 3 and all(not r.get("output") for r in rows[-3:]):
            print("Stopped after three consecutive requests without output. Check provider access before rerunning.", flush=True)
            break


if __name__ == "__main__":
    main()
