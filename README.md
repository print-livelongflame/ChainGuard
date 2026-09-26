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

Install the LLM provider dependency:

```bash
pip install -r requirements.txt
```

The CLI starts with OpenAI. Type `change ai` to select OpenAI, Gemini, or
Claude for all LLM-backed agents in the current session. Configure a key in
the environment or as the matching constant in `api_keys/api_keys.py`:

| Provider | Environment variable | `api_keys.py` constant |
| --- | --- | --- |
| OpenAI | `OPENAI_API_KEY` | `OPENAI_API_KEY` |
| Gemini | `GEMINI_API_KEY` | `GEMINI_API_KEY` |
| Claude | `ANTHROPIC_API_KEY` or `CLAUDE_API_KEY` | `CLAUDE_API_KEY` |

Values such as `"Enter key here"` are treated as unset.

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

## External detector registration

The detection algorithm is hosted outside this repository. To register it with
the BA, edit `detector_config.json` in the project root and set `enabled` to
`true`, `name` to the detector name, and `endpoint` to the detector service's
HTTP endpoint.

The BA reads this configuration on every request. Its task output, including
`address_info`, will contain:

```json
"selected_detector": "my_custom_scam_detector",
"detector_configured": true
```

Set `enabled` to `false` or remove `detector_config.json` to return to
`null` / `false`. Invalid configuration produces an error instead of silently
reporting no detector. Registration describes setup; it does not check endpoint
availability.

The optional `mode`, `required_input_type`, and `is_llm_based` settings default
to `template`, `address_with_context`, and `false` for existing registrations.

### Detector configuration fields

`detector_config.json` must remain valid JSON, so do not add `//` comments
inside the file. The fields mean:

- `enabled`: set to `true` to allow the CLI to call the external detector; set
   to `false` to disable it.
- `name`: the display name used for the selected detector in BA task output.
- `endpoint`: the external detector's HTTP `POST /detect` URL.
- `mode`: use `template` for the standard `AddressContext` and
   `DetectionResult` contract. `generic` is reserved for future custom mapping.
- `required_input_type`: use `address_with_context` when the detector needs
   fetched blockchain data, or `address` when it only needs the address.
- `is_llm_based`: set to `true` only when the external detector itself uses an
   LLM; this is metadata and does not change how the request is sent.

If the detector requires authentication, set `DETECTOR_API_KEY` in the shell
where ChainGuard runs. The key is sent as the `X-API-Key` header and should not
be stored in `detector_config.json`.

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

The shared detector contract is:

```text
fetcher data -> AddressContext -> detect() -> DetectionResult
```


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