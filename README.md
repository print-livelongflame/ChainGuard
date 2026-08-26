# ChainGuard

AI LLM which wil help users to investigate blockchain wallet address

---

# Setup the Project

So far setting up the project will be very simple. Just add a `touch api_keys\api_keys.py`. Inside the file add you api keys.

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
