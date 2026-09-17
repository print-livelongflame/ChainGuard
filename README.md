# ChainGuard

AI LLM which wil help users to investigate blockchain wallet address

---

# Setup the Project

So far setting up the project will be very simple. Just add a file at `api_keys\api_keys.py`. Inside the file add your api keys.

```python
'''
Enter your keys here
'''
ETHERSCAN_API_KEY = "xxxxxxxxx"
OPENAI_API_KEY = "xxxxxxxxx"
```

## Run ChainGuard

Start the interactive CLI from the project root:

```bash
python -m src.main
```

## Test Individual Fetchers

Run a fetcher with `-test` to enter an address, check whether JSON is returned,
and save the response in `fetchers/json_files_test/`:

```bash
python -m fetchers.contract_fetcher -test
python -m fetchers.etherscan -test
python -m fetchers.honeypot -test
python -m fetchers.rugcheck -test
python -m fetchers.liquidty_pairedPool_fetcher -test
python -m fetchers.transaction_history_fetcher -test
```

The transaction resolver uses a transaction hash instead:

```bash
python -m fetchers.tx_hash_resolver_fetcher -test
```

The contract-address resolver uses a token name and symbol instead:

```bash
python -m fetchers.contract_address_fetcher -test
```

## Explaining Data Fetcher Components

| Data Fetcher      | Purpose           | Project File(s)   |
| ----------------- | ----------------- | ----------------- |
| Contract Fetcher | Bytecode, ABI (if verified), creator, creation tx | `fetchers\contract_fetcher.py` |
| Transaction History Fetcher | Recent transactions in/out | `fetchers\transaction_history_fetcher.py` |
| Token Info Fetcher | Token balances and metadata held by the address | `fetchers\token_info_fetcher.py` |
| Liquidity / paired-pool Fetcher | DEX pool pairing, liquidity depth, recent add/remove events | `fetchers\liquidty_pairedPool_fetcher.py` |
| Tx-hash Resolver Fetcher | Given a tx hash, look up the transaction and extract the address(es) involved | `fetchers\tx_hash_resolver_fetcher.py` |
| Contract Address Resolver Fetcher | Given a token name/symbol, resolve possible contract addresses (best-effort, flag ambiguous matches rather than guessing) | `fetchers\contract_address_fetcher.py` |

---

# API and detector architecture

The API has two key stages:

1. Fetcher stage
   - Existing fetchers are run against the address.
   - The CLI already contains this logic in `src/main.py` via `fetch_results()`.

2. Context-building stage
   - `src/context_builder.py` takes the raw fetcher output and converts it into a single `AddressContext` object.
   - This normalises the data into a structure that the detector can use without needing to know the internal details of every fetcher.

The builder is important because the detector should receive consistent data, not a pile of raw fetcher results with different formats and skip/fail states.

## Why the context builder exists

The fetchers do not all return the same thing:
- some return a list of transactions
- some return a single contract object
- some return token transfer data
- some return a list of liquidity pools
- some are skipped or fail

The context builder does this:

```python
results, address_analysis = fetch_results(address)
```

Then it turns that into:

```python
AddressContext(
    address=address,
    address_analysis=address_analysis,
    contract=...,
    tx_history=...,
    tokens=...,
    liquidity=...,
    queried_at=...,
    fetcher_provenance=...,
)
```

This keeps the detector logic simple and future-proof.

---

# Running API wrapper and adding personal detection logic 
In order to add your own detection logic you can go ahead and go to `detector_template\detector.py` and add your own logic there. From there you can run `python -m uvicorn app:app --reload --port 9000` in termainl to start the wrapper. 

## Basic API flow

### Register a custom detector with the BA

After adding your algorithm to `detector_template/detector.py`, edit
`detector_config.json` in the project root.
Set `name` to your detector's name and `endpoint` to its FastAPI `/detect` URL.
Keep `enabled` set to `true` to register it. Start the wrapper from the project
root with:

```bash
python -m uvicorn detector_template.app:app --reload --port 9000
```

The BA reads this shared configuration on every request. Its task output,
including `address_info`, will contain:

```json
"selected_detector": "my_custom_scam_detector",
"detector_configured": true
```

`GET /configuration` on the wrapper reports the same fields. Set `enabled` to
`false` or remove `detector_config.json` to return to `null` / `false`. Invalid
configuration produces an error instead of silently reporting no detector.
The bundled example alone does not count as a custom detector; register your
implementation explicitly. Registration describes setup and does not check
endpoint availability. A configured detector currently produces an integration
placeholder for scam checks, without fetching context or invoking SCH or the detector.
Address information requests continue to run their requested fetchers.
The optional `mode`, `required_input_type`, and `is_llm_based` settings default
to `template`, `address_with_context`, and `false` for existing registrations.
Generic request/response mapping and detector execution remain unimplemented.

The intended architecture is:

```text
address
   â†“
existing fetchers
   â†“
AddressContext
   â†“
detect(context)
```

There are two main API routes:

- `POST /detect`  -> accepts an already-created `AddressContext`
- `POST /analyse` -> takes an address, runs the fetchers, builds the `AddressContext`, then passes it to the detector
- `POST /resolve-contract-address` -> takes a token name/symbol and returns possible contract address matches

---

# Current detector template

The detector template is intentionally simple for now. It is designed to verify that:

```text
fetcher data -> AddressContext -> detect() -> DetectionResult
```

works correctly before moving to a more advanced scam detection model.

The template is a stub returning `insufficient_evidence` until its detection
algorithm is implemented. It shares the same labels and weighted evidence
contract as SCH.


## CLI Scam Checker

Run `python -m src.main` from the project root. For example, ask
`Is 0x0000000000000000000000000000000000000000 a scam?`.

For an in-scope `scam_check` with no configured detector, BA resolves the target
and fetches contract, transaction, token and liquidity context. SCH receives
that BA task and its saved `AddressContext`, then produces an assessment and
explanation in one LLM call. The Forensic
Investigator is not called, as the Scam Checker creates it's own LLM plain text response. Fetcher failures remain visible in provenance;
missing evidence must not be interpreted as safety.

The CLI's **Scam Checker output** section identifies the LLM source and prints
the validated flat JSON contract: `label` (`scam`, `not_scam`, or
`insufficient_evidence`), `risk_type`, `confidence` (0 to 1), `evidence` (objects
with `description` and `weight`, 0 to 1), and `explanation`. The optional
`reasoning_trace` is null in the current zero-shot strategy and omitted from
CLI output. The context file remains separate from this result. Invalid model
responses or API failures show an assessment-unavailable message, never a verdict.

After the structured diagnostic output, the normal `Response:` section shows
SCH's plain-language `explanation`, and the CLI returns to the next `You:` prompt.
Only that explanation is added as the assistant reply in conversation history;
the structured result stays in the Scam Checker output area.

Shared consumers now use `tx_history` and `tokens`, rather than the old
`transactions`/`token` aliases, and structured evidence rather than strings.