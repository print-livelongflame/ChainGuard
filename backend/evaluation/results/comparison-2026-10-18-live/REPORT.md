# Prompt strategy evaluation

Provider: openai; model: openai/gpt-4.1-mini; temperature: 0.2; repeats: 3.

Completed trials: 180 / 180. Failed trials: 2.

Synthetic, author-labelled cases. No real-world detection accuracy claim. Objective scores exclude explanation quality; FI requires human review. Errors count as failed trials. Repeats of a case are not independent cases.

| Agent | Strategy | Valid | Objective pass | Same decision | Mean seconds |
|---|---|---:|---:|---:|---:|
| business_analyser | chain_of_thought | 100.0% | 83.3% | 100.0% | 1.26 |
| business_analyser | few_shot | 100.0% | 83.3% | 100.0% | 1.21 |
| business_analyser | zero_shot | 88.9% | 88.9% | 83.3% | 1.34 |
| forensic_investigator | chain_of_thought | 100.0% | n/a | n/a | 1.01 |
| forensic_investigator | few_shot | 100.0% | n/a | n/a | 0.85 |
| forensic_investigator | zero_shot | 100.0% | n/a | n/a | 1.03 |
| scam_checker | chain_of_thought | 100.0% | 96.7% | 90.0% | 1.93 |
| scam_checker | few_shot | 100.0% | 86.7% | 90.0% | 1.37 |
| scam_checker | zero_shot | 100.0% | 83.3% | 90.0% | 1.41 |

Review blind-review.csv before opening review-key.json. Score each dimension 0 (fails), 1 (partial), 2 (fully meets rubric). Do not infer a winner from latency or JSON validity alone. No significance test or universal superiority claim is provided.

## Objective failures

- sch-honeypot, zero_shot, repeat 1: label, risk_type.
- sch-injected-metadata, zero_shot, repeat 3: label.
- sch-injected-metadata, chain_of_thought, repeat 3: label.
- ba-ambiguous, few_shot, repeat 3: clarify.
- ba-ambiguous, few_shot, repeat 1: clarify.
- ba-ambiguous, chain_of_thought, repeat 3: clarify.
- sch-honeypot, zero_shot, repeat 2: label, risk_type.
- ba-ambiguous, chain_of_thought, repeat 2: clarify.
- ba-concept, zero_shot, repeat 1: ValueError.
- ba-ambiguous, few_shot, repeat 2: clarify.
- sch-injected-metadata, few_shot, repeat 3: label.
- sch-injected-metadata, few_shot, repeat 2: label.
- sch-honeypot, few_shot, repeat 1: label, risk_type.
- ba-ambiguous, chain_of_thought, repeat 1: clarify.
- sch-injected-metadata, few_shot, repeat 1: label.
- sch-injected-metadata, zero_shot, repeat 1: label.
- ba-concept, zero_shot, repeat 3: ValueError.
- sch-injected-metadata, zero_shot, repeat 2: label.
