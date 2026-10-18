# Findings from the first live comparison

All 180 planned requests completed using `openai/gpt-4.1-mini`, temperature 0.2,
the production agent prompts and token budgets, and three repetitions per case.
No saved admin settings were changed. Two BA requests failed with `ValueError`;
the runner deliberately retained only exception types, so their precise causes
cannot be established from this log. They count as failures. Provider usage was
available for 178 requests, totalling 304,787 reported tokens; failed-request
usage and billing are unknown. The preceding sandbox-blocked attempt is in a
separate directory and is excluded from these model scores.

| Agent | Zero-shot | Chain-of-thought | Few-shot |
|---|---:|---:|---:|
| SCH objective passes | 25/30 (83.3%) | 29/30 (96.7%) | 26/30 (86.7%) |
| BA objective passes | 16/18 (88.9%) | 15/18 (83.3%) | 15/18 (83.3%) |
| FI nonempty successful responses | 12/12 | 12/12 | 12/12 |

**FI success is not an explanation-quality score.** Blind rubric scoring remains
to be completed before making a claim about the best FI strategy. The review
spreadsheet contains all three agents and can also expose issues missed by the
automatic BA/SCH checks.

## What supports the SCH default

Chain-of-thought had the highest observed objective pass rate on these ten SCH
cases: 13.3 percentage points above zero-shot and 10.0 points above few-shot.
Zero-shot misclassified both an owner-restricted sale scenario and injected
metadata; chain-of-thought avoided the former in all three repetitions but still
misclassified the latter once. Few-shot misclassified injected metadata in all
three repetitions and the owner-restricted sale scenario once.

Mean SCH latency was 1.93 seconds for chain-of-thought, 1.41 for zero-shot, and
1.37 for few-shot. These are end-to-end request measurements in one shuffled
sequential run, including provider and network variability, not intrinsic model
speed. All SCH strategies had valid structured output and consistent decisions
across repeats for 9/10 cases. Consistency alone did not establish correctness.

## BA findings

Zero-shot had the highest observed overall pass rate despite two request failures.
Chain-of-thought and few-shot each failed the ambiguous-intent case in all three
repetitions: they selected fetch fields rather than asking the required
clarification. This offers limited support for retaining BA zero-shot, while the
failed zero-shot requests deserve investigation before a stronger reliability
claim. Automatic checks cover the declared expected fields, not every possible
routing or extraction error.

## Wording suitable for the project report

> In a synthetic pilot evaluation using GPT-4.1-mini at temperature 0.2 and the
> application's production output limits, the Scam Checker's chain-of-thought
> prompt achieved 29/30 objective passes (96.7%), compared with 25/30 (83.3%) for
> zero-shot and 26/30 (86.7%) for few-shot. This supports its selection as the SCH
> default within this tested configuration, at the cost of higher observed mean
> latency. These results do not establish statistical significance, universal
> superiority, or real-world scam-detection accuracy.

## Limits and next experiment

There are ten unique SCH cases, not thirty independent examples; eight expect
insufficient evidence and two expect scam. There is no SCH `not_scam` reference
case. Labels are synthetic author judgments and some concepts overlap the prompt
demonstrations. Original base prompts already contain examples and detailed
rules. This tests these concrete prompt additions rather than pure textbook
strategy categories, and cannot verify internal chain-of-thought execution.

An injected-metadata case failed under every strategy at least once. Prompt
strategy is therefore insufficient to establish injection resistance. Preserve
this result, and evaluate any future mitigation on a separate held-out dataset.

Complete blind review, add independently reviewed held-out evidence snapshots
covering all verdicts, and repeat across more cases. Then run a separate
temperature experiment with equal settings across strategies. Do not tune these
prompts on this dataset and report the same cases as unseen evaluation evidence.
