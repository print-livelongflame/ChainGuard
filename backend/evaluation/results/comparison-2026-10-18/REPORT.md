# Prompt strategy evaluation

Provider: openai; model: openai/gpt-4.1-mini; temperature: 0.2; repeats: 3.

Synthetic, author-labelled cases. No real-world detection accuracy claim. Objective scores exclude explanation quality; FI requires human review. Errors count as failed trials. Repeats of a case are not independent cases.

| Agent | Strategy | Valid | Objective pass | Same decision | Mean seconds |
|---|---|---:|---:|---:|---:|
| forensic_investigator | chain_of_thought | 0.0% | n/a | n/a | 1.46 |
| forensic_investigator | few_shot | 0.0% | n/a | n/a | 1.34 |
| scam_checker | chain_of_thought | 0.0% | 0.0% | n/a | 20.77 |

Review blind-review.csv before opening review-key.json. Score each dimension 0 (fails), 1 (partial), 2 (fully meets rubric). Do not infer a winner from latency or JSON validity alone. No significance test or universal superiority claim is provided.
