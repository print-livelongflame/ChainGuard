# Fetcher cache benchmark

Run from `backend`:

```bash
python -m evaluation.cache_benchmark
```

The default run performs 30 repeat lookups through ChainGuard's production
`run_fetcher` cache wrapper. It compares uncached requests with cold-cache and
warm-cache requests, using a deterministic local fixture that simulates a 50 ms
upstream delay. It writes `REPORT.md`, `summary.json`, and per-trial `trials.csv`
under `evaluation/results/cache-benchmark-<timestamp>/`.

This benchmark makes no blockchain API or LLM calls. It measures local cache
overhead, the simulated repeat-request latency reduction, and whether warm hits
avoid source calls. Its timing result is not a live-provider latency claim. For a
different fixture delay or repetition count, use `--simulated-upstream-ms` and
`--repeats`; use `--output` to choose a report directory.

Example:

```bash
python -m evaluation.cache_benchmark --repeats 30 --simulated-upstream-ms 50
```
