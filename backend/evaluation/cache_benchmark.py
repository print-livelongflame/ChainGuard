"""Offline benchmark for ChainGuard's production fetcher cache wrapper.

Run from ``backend`` with ``python -m evaluation.cache_benchmark``. The fake
upstream fetcher has a configurable delay; no blockchain or LLM service is called.
"""

import argparse
import csv
import json
import math
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from unittest.mock import patch

from src import main
from src.fetcher_cache import (
    build_fetcher_cache_key,
    read_fetcher_cache,
    write_fetcher_cache,
)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def measure(callable_) -> tuple[dict, float]:
    started = time.perf_counter()
    result = callable_()
    return result, (time.perf_counter() - started) * 1000


def run_benchmark(repeats: int, delay_ms: float, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    calls = 0

    def fake_fetcher(address: str, chain_id: int = 1) -> dict:
        nonlocal calls
        calls += 1
        time.sleep(delay_ms / 1000)
        return {"address": address, "chain_id": chain_id, "fixture": "stable"}

    module_name = "evaluation._cache_benchmark_fake_fetcher"
    fake_module = ModuleType(module_name)
    fake_module.get_fixture = fake_fetcher
    cache_key = build_fetcher_cache_key(
        "cache_benchmark",
        module_name,
        "get_fixture",
        ("0x0000000000000000000000000000000000000001",),
        {"chain_id": 1},
    )
    address = "0x0000000000000000000000000000000000000001"
    uncached_times: list[float] = []
    warm_times: list[float] = []
    rows: list[dict] = []
    warm_hit_count = 0
    expected_data = {"address": address, "chain_id": 1, "fixture": "stable"}

    with TemporaryDirectory(prefix="chainguard-cache-benchmark-") as temporary:
        cache_dir = Path(temporary)
        cache_path = cache_dir / f"{cache_key}.json"
        with patch.dict(sys.modules, {module_name: fake_module}), \
             patch.object(
                 main,
                 "read_fetcher_cache",
                 side_effect=lambda key, ttl: read_fetcher_cache(key, ttl, cache_dir),
             ), \
             patch.object(
                 main,
                 "write_fetcher_cache",
                 side_effect=lambda key, data, ttl: write_fetcher_cache(
                     key, data, ttl, cache_dir
                 ),
             ):
            for trial in range(1, repeats + 1):
                calls_before = calls
                uncached, uncached_ms = measure(
                    lambda: main.run_fetcher(
                        "cache_benchmark", module_name, "get_fixture", address,
                        chain_id=1,
                    )
                )
                if calls - calls_before != 1 or uncached["data"] != expected_data:
                    raise RuntimeError("Uncached baseline did not call the fixture exactly once.")
                uncached_times.append(uncached_ms)

                cache_path.unlink(missing_ok=True)
                calls_before = calls
                cold, cold_ms = measure(
                    lambda: main.run_fetcher(
                        "cache_benchmark", module_name, "get_fixture", address,
                        chain_id=1, cache_ttl_seconds=300,
                    )
                )
                if calls - calls_before != 1 or cold["data"] != expected_data:
                    raise RuntimeError("Cold-cache request did not call the fixture exactly once.")

                calls_before = calls
                warm, warm_ms = measure(
                    lambda: main.run_fetcher(
                        "cache_benchmark", module_name, "get_fixture", address,
                        chain_id=1, cache_ttl_seconds=300,
                    )
                )
                if calls != calls_before or warm["data"] != expected_data:
                    raise RuntimeError("Warm-cache request called the fixture or changed its result.")
                if warm.get("cache", {}).get("source") != "disk":
                    raise RuntimeError("Warm-cache request was not served from disk.")

                warm_hit_count += 1
                warm_times.append(warm_ms)
                rows.append({
                    "trial": trial,
                    "uncached_ms": round(uncached_ms, 4),
                    "cold_cache_ms": round(cold_ms, 4),
                    "warm_cache_ms": round(warm_ms, 4),
                    "uncached_source_calls": 1,
                    "cold_cache_source_calls": 1,
                    "warm_cache_source_calls": 0,
                })

    median_uncached = statistics.median(uncached_times)
    median_warm = statistics.median(warm_times)
    latency_reduction = (
        (median_uncached - median_warm) / median_uncached * 100
        if median_uncached else 0.0
    )
    summary = {
        "benchmark": "production fetcher cache wrapper with a deterministic local fixture",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "repeats": repeats,
        "simulated_upstream_delay_ms": delay_ms,
        "external_api_calls": 0,
        "llm_calls": 0,
        "upstream_calls_uncached": repeats,
        "upstream_calls_cold_cache": repeats,
        "upstream_calls_warm_cache": 0,
        "warm_cache_hit_rate": warm_hit_count / repeats,
        "median_uncached_ms": round(median_uncached, 4),
        "p95_uncached_ms": round(percentile(uncached_times, 0.95), 4),
        "median_warm_cache_ms": round(median_warm, 4),
        "p95_warm_cache_ms": round(percentile(warm_times, 0.95), 4),
        "median_repeat_latency_reduction_percent": round(latency_reduction, 2),
        "interpretation": (
            "Local simulated-upstream result; measures cache overhead and avoided "
            "source calls, not live blockchain-provider latency."
        ),
    }

    with (output_dir / "trials.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    report = f"""# Fetcher cache benchmark

This offline benchmark exercised ChainGuard's production `run_fetcher` cache
wrapper with a deterministic local fixture. The fixture simulated an upstream
delay of {delay_ms:g} ms. No blockchain provider, external API, or LLM was called.

| Measure | Result |
|---|---:|
| Repeated lookup trials | {repeats} |
| Warm-cache hit rate | {warm_hit_count / repeats:.0%} |
| Source calls without cache | {repeats} |
| Source calls on warm cache | 0 |
| Median uncached lookup | {median_uncached:.2f} ms |
| Median warm-cache lookup | {median_warm:.2f} ms |
| Median repeat-latency reduction | {latency_reduction:.2f}% |

These timings describe a local simulated-upstream benchmark. They do not estimate
real blockchain-provider latency or establish production-wide performance gains.
Use `trials.csv` for per-trial timings and `summary.json` for machine-readable results.
"""
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    return summary


def main_cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--simulated-upstream-ms", type=float, default=50)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 1 or args.simulated_upstream_ms < 0:
        parser.error("repeats must be positive and simulated delay cannot be negative")
    output_dir = args.output or Path("evaluation/results") / (
        "cache-benchmark-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    summary = run_benchmark(args.repeats, args.simulated_upstream_ms, output_dir)
    print(json.dumps(summary, indent=2))
    print(f"Report written to {output_dir / 'REPORT.md'}")


if __name__ == "__main__":
    main_cli()
