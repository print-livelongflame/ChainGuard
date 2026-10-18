# Scam assessment evaluation

This evaluation runs ChainGuard's Scam Checker on 20 Ethereum contract addresses: 10 marked with rug-pull patterns and 10 weak-negative examples. Labels and addresses come from CRPWarner's published ground-truth workbook. Its all-zero rows mean the workbook marks none of its three tested contract patterns; they do **not** prove a contract is safe. Treat this as a small preliminary evaluation, not a general scam-detection accuracy claim.

The runner's default mode validates and previews the dataset without fetching blockchain data or calling an LLM. Running with `--run` fetches each address's contract, transaction, token, and liquidity evidence through ChainGuard, then makes one Scam Checker request per address (20 model requests total). Existing fetcher cache entries may reduce blockchain requests. AI-provider usage may be billable; no assessment calls happen during preview.

From the `backend/` directory:

```bash
python -m evaluation.run_scam_eval
python -m evaluation.run_scam_eval --run
```

Each completed case is saved to a timestamped JSON report under `evaluation/results/`. The report includes exact agreement, per-label counts, a confusion matrix, confidence, evidence, explanations, source links, and fetcher status. `insufficient_evidence` counts as non-matching in exact agreement and remains visible in the confusion matrix.

Sources: [CRPWarner ground-truth workbook](https://github.com/CRPWarner/RugPull/blob/main/dataset/groundtruth/groundTruth.xlsx) and [CRPWarner repository documentation](https://github.com/CRPWarner/RugPull), which describes its manually analyzed rug-pull patterns and reported sources.
