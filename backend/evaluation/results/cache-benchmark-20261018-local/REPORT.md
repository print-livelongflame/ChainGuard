# Fetcher cache benchmark

This offline benchmark exercised ChainGuard's production `run_fetcher` cache
wrapper with a deterministic local fixture. The fixture simulated an upstream
delay of 50 ms. No blockchain provider, external API, or LLM was called.

| Measure | Result |
|---|---:|
| Repeated lookup trials | 30 |
| Warm-cache hit rate | 100% |
| Source calls without cache | 30 |
| Source calls on warm cache | 0 |
| Median uncached lookup | 54.65 ms |
| Median warm-cache lookup | 0.41 ms |
| Median repeat-latency reduction | 99.25% |

These timings describe a local simulated-upstream benchmark. They do not estimate
real blockchain-provider latency or establish production-wide performance gains.
Use `trials.csv` for per-trial timings and `summary.json` for machine-readable results.
