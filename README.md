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
    transactions=...,
    token=...,
    liquidity=...,
    honeypot=...,
    rugcheck=...,
    tx_hash=...,
    raw_results=results,
)
```

This keeps the detector logic simple and future-proof.

---

# Running API wrapper and adding personal detection logic 
In order to add your own detection logic you can go ahead and go to `detector_template\detector.py` and add your own logic there. From there you can run `python -m uvicorn app:app --reload --port 9000` in termainl to start the wrapper. 

## Basic API flow

The intended architecture is:

```text
address
   ↓
existing fetchers
   ↓
AddressContext
   ↓
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

For a basic example, the template can simply inspect whether contract data, honeypot data, or risk indicators are present and return a label like `low_risk` or `medium_risk`.

---

# Next step

Once the API flow is working, the next extension will be the LLM layer. But for now our goal is just to keep the architecture clean and easy to extend.
