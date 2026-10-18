# Compare agent prompt strategies

From `backend`, run:

```powershell
python -m evaluation.run --output evaluation/results/my-run --dry-run
python -m evaluation.run --output evaluation/results/my-run
```

The default run makes **180 live model calls**: 20 synthetic cases × 3 strategies
× 3 repetitions. It uses the configured SCH provider for every agent, the actual
production agent functions and saved per-agent token limits, and temperature 0.2 for every
strategy. It does not modify saved admin settings or call blockchain fetchers.
Each request has fresh conversation state. Request order is shuffled with a saved
seed. Provider-internal retries can result in more HTTP attempts than model calls.

Use `--agents scam_checker` for SCH only (90 calls). Set `--repeats 1` for a pilot.
To study temperature separately, repeat the complete experiment with
`--temperature 0.1` or `--temperature 0.4` and a new output directory. Do not compare
different strategies at different temperatures and attribute the difference solely
to prompting. Baseline prompts already contain explicit rules and examples, so
the experiment compares the app's strategy additions, not textbook pure zero-shot
against pure few-shot. Chain-of-thought means a request for private analysis; this
experiment cannot observe or verify the model's internal reasoning process.

Outputs:

- `REPORT.md` and `summary.csv`: validity, all-or-nothing objective task pass,
  repeated decision consistency, latency, and provider-reported token totals.
- `trials.jsonl`: every final answer, exact composed messages, schema, configured token limit,
  timing, usage when available, and task checks. Failures remain in denominators.
- `manifest.json`: provider/model, time, seed, temperature, token limits and hashes.
- `cases.json`: frozen test inputs, expected decisions and review rubrics.
- `blind-review.csv`: answers in shuffled order without strategy names.
- `review-key.json`: mapping for analysis **after** blind scoring.

For an exportable count chart, install matplotlib if needed and run
`python -m evaluation.plot evaluation/results/my-run`. This writes PNG and SVG
figures. FI is omitted because it has no automatic semantic score.

Review every answer for factual support, task fidelity, uncertainty and clarity.
Give each dimension 0 (fails), 1 (partial) or 2 (fully meets its case rubric).
For FI, preserve the detector's verdict, confidence and evidence; an unsupported
change fails task fidelity. For SCH, invented checks or treating failed fetches as
evidence fail factual support. A JSON-valid answer can still be wrong. FI has no
automatic semantic accuracy score; do not treat a nonempty explanation as faithful.
Have a second reviewer score independently if available, and record disagreements.
Do not open the strategy key until scores are final. The writing may itself reveal
strategy, so blinding is partial.

These cases are a **pilot benchmark**, not independently verified real-world scam
ground truth. The case mix is intentionally heavy on insufficient evidence, and
does not yet include a defensible `not_scam` SCH case. Report per-case outcomes,
not just aggregate accuracy. A three-repeat run estimates variability but is small;
repetitions of the same case are not independent samples. The cases overlap in
concepts with few-shot demonstrations, which can favour few-shot. Add a separately
reviewed, held-out set of diverse frozen evidence snapshots before making a strong
claim or tuning prompts. Freeze expected answers and rubrics before seeing results.

Suggested report wording:

> On this synthetic benchmark, using [model], temperature [x], and the production
> token limits, [strategy] achieved [x/y] correct SCH decisions and a mean blind
> review score of [x/8], compared with [other results]. These results [support/do
> not support] our default for this tested setup. They do not demonstrate universal
> superiority or real-world scam-detection accuracy.

If results tie, say so. If another strategy wins, revise the default or expand the
held-out evaluation. Preserve failures caused by output limits: a larger equal
budget experiment is a separate condition, not a replacement for a poor result.
No model judge is used and no statistical significance is asserted by this runner.
