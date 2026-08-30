# ChainGuard

AI LLM which wil help users to investigate blockchain wallet address

---

# Setup the Project

So far setting up the project will be very simple. Just add a file at `api_keys\api_keys.py`. Inside the file add your api keys.

```python
'''
Enter your keys here
'''
ETHERSCAN_API_KEY= "xxxxxxxxx"
```

## Run ChainGuard

Start the interactive CLI from the project root:

```bash
python3 -m src.main
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
## Explaining Data Fetcher Components

| Data Fetcher      | Purpose           | Project File(s)   |
| ----------------- | ----------------- | ----------------- |
| Contract Fetcher | Bytecode, ABI (if verified), creator, creation tx | `fetchers\contract_fetcher.py` |
| Transaction History Fetcher | Recent transactions in/out | `fetchers\transaction_history_fetcher.py` |
| Token Info Fetcher | Token balances and metadata held by the address | `fetchers\token_info_fetcher.py` |
| Liquidity / paired-pool Fetcher | DEX pool pairing, liquidity depth, recent add/remove events | `fetchers\liquidty_pairedPool_fetcher.py` |
| Tx-hash Resolver Fetcher | Given a tx hash, look up the transaction and extract the address(es) involved | `fetchers\tx_hash_resolver_fetcher.py` |
| Token-name Resolver Fetcher | Given a token name/symbol, resolve to a contract address (best-effort — flag ambiguous matches rather than guessing) | `PENDING` |

---

# Running API wrapper and adding personal detection logic 
In order to add your own detection logic you can go ahead and go to `detector_template\detector.py` and add your own logic there. From there you can run `python -m uvicorn app:app --reload --port 9000` in termainl to start the wrapper. 