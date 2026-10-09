# ChainGuard

AI LLM which wil help users to investigate blockchain wallet address

## Project Layout

- `backend/` contains the Python CLI, chat API, fetchers, detectors, and AI integrations.
- `frontend/` contains the React/Vite web chat.

## Quick Start (Docker)

Install Docker Desktop on Windows/macOS, or Docker Engine with the Compose plugin
on Linux. Clone ChainGuard and the independent detector repository side by side:

```text
Projects/
├── ChainGuard/
└── ChainGuard-detector-template/
```

```powershell
git clone https://github.com/print-livelongflame/ChainGuard.git
git clone https://github.com/Mossata/ChainGuard-detector-template.git
cd ChainGuard
Copy-Item .env.example .env
```

On macOS/Linux, use `cp .env.example .env` in place of `Copy-Item`. Edit `.env`
if you use a custom detector path or prefer to configure keys before startup.
Otherwise, the default sibling detector path works without `.env`. You can also
enter keys after startup under **Settings → API Keys**; chat stays unavailable
until the selected LLM provider key is configured. Etherscan is needed for
Ethereum fetcher data. `.env` is ignored by Git and secrets are passed only to
backend/detector containers, never to the frontend.

Then start the app from the ChainGuard directory:

```powershell
docker compose up
```

Open <http://localhost:5173>. Compose builds dependencies automatically. The
detector path defaults to `../ChainGuard-detector-template`, relative to this
project directory. For a fork or custom detector next to ChainGuard, set the
path in `.env`, for example `DETECTOR_PATH=../my-custom-detector`. The chosen
detector repository must have a root `Dockerfile`, `requirements.txt`, and the
template-compatible `app.py`/`/health` and `/detect` API. A missing detector
directory or Dockerfile makes Compose stop with a build/mount error; clone the
detector next to ChainGuard or correct `DETECTOR_PATH` before retrying. The
detector does not silently fall back to an empty folder.

```powershell
docker compose down
docker compose up --build
docker compose restart detector
```

The first command stops the stack; the second rebuilds local images after
ChainGuard source or dependency changes; the third restarts the detector after
editing mounted detector code. Editing detector dependencies requires rebuilding
its image with `docker compose up --build detector`.

### Docker architecture

```text
Browser
   │ http://localhost:5173
   ▼
ChainGuard frontend (Vite)
   │ /api → http://backend:8000
   ▼
ChainGuard backend (FastAPI)
   │ POST /detect → http://detector:9000
   ▼
Detector service container
   │ /app is a bind mount, not code copied into the ChainGuard image
   ▼
User's separate detector repository (DETECTOR_PATH)
```

The host ports are `5173` (web app), `8000` (backend API), and `9000` (detector
health/docs/debug access); all are bound to localhost only. Container-to-container
traffic uses Compose service names. Docker builds the frontend/backend from this
checkout, and builds the detector runtime from the detector repository's own
Dockerfile. The detector source remains in the mounted repository; edit it on
the host and restart the detector container to load changes. The detector
settings page writes settings to a named Docker volume, so they persist across
container restarts.

The official template starts with a stub response. Replace its `detector.py`
implementation with your algorithm before treating results as meaningful. No
Docker setup can provide LLM or blockchain API credentials automatically; valid
provider keys must be supplied in `.env`.

## Development setup without Docker

Configure backend keys as described below, then use two terminals from the
repository root.

**Terminal 1 — API:**

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --workers 1
```

**Terminal 2 — frontend:**

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`). On other
shells, `npm` can be used instead of `npm.cmd`. Vite proxies `/api` to port 8000;
keep the browser on the Vite URL so session cookies and downloads use the same origin.

Select **New Chat**, or type in the welcome screen to create a chat automatically.
Enter sends a message; Shift+Enter adds a newline. Use the paperclip button to
attach one UTF-8 `.txt` or `.json` file (up to 50 KB) to a message. Suggestion
cards fill an editable prompt. Replace address placeholders with a complete
Ethereum address. Replies can include JSON download links. The sidebar switches between conversations,
including while another conversation is processing.

The web API uses OpenAI by default. To select another configured provider, set
`$env:CHAINGUARD_AI_PROVIDER = "gemini"` (or `"claude"` / `"openai"`) in the API
terminal before starting it. Restart the API after changing the selected
provider; API keys saved through Settings apply without a restart. Keys stay on
the backend; do not put them in frontend environment variables.

In the web app, open **Settings → API Keys** to enter or remove provider,
Etherscan, and detector keys. Save keys to apply them immediately. The page
shows only whether a key is configured; it never reads a saved secret back into
the browser. The backend writes the values as plaintext constants in
`backend/api_keys/api_keys.py`. This folder is ignored by Git and, in Docker,
bind-mounted from the host so the file is created/updated in the local checkout.
Anyone with access to that file can read its keys; use this local-only page only
on a trusted machine, never commit the file, and rotate credentials if it was
ever shared. If a provider key is already supplied by `.env`, update/remove it
there too so the environment does not override the saved file after restart.

This is a local demo with no accounts. An HTTP-only cookie identifies each browser
session; the selected chat ID is kept in local storage. Chat transcripts and internal
model history remain in server memory. Refreshing the page restores the chats and
checks any pending reply. Restarting the API expires all chats. JSON downloads are
temporary files removed on normal server shutdown. Run **one worker**; additional
workers would have independent session stores. Do not expose this development
configuration as a public service.

### Web API

| Method and path | Behavior |
| --- | --- |
| `GET /api/chats` | Session chats, configured provider, and configuration errors |
| `POST /api/chats` | Create an empty chat |
| `GET /api/chats/{id}` | Transcript and processing state |
| `POST /api/chats/{id}/messages` | Send `{ "text": "your question", "attachments": [{ "name": "notes.txt", "content": "..." }] }`; return completed chat |
| `GET /api/chats/{id}/files/{file_id}` | Download an attached JSON result |
| `GET /api/settings/detector` | Read the saved external detector configuration |
| `POST /api/settings/detector` | Validate and save external detector settings to `backend/detector_config.json` |
| `GET /api/settings/api-keys` | Return configured/not-configured status only; never returns key values |
| `POST /api/settings/api-keys` | Create, update, or remove local API-key constants |

Chats expose `id`, `title`, `created_at`, `messages`, `processing`, and `error`.
Messages contain `id`, `role`, `text`, `created_at`, and `attachments`; attachments
contain `id`, `name`, and an optional `url`. Uploaded file contents are provided
to the model as untrusted reference data and are not stored as downloads. Internal BA task JSON is never included in the
visible transcript. Only one turn may run per chat (`409` for overlapping sends).
Messages must contain 1–12,000 characters after trimming. Unknown chats or files
return `404`; unavailable provider configuration returns `503` before accepting a turn.
An accepted turn continues after a browser disconnect. Clients can query its chat
to recover the result; they should not automatically resend a failed HTTP request.

### Checks

```powershell
cd backend
python -m unittest discover -s tests -v
```

```powershell
cd frontend
npm.cmd run build
npm.cmd run lint
```

Backend tests mock the provider and external work, so they do not need keys or
make paid requests. To smoke-test configured integrations, ask a general blockchain
question, then request contract information for a complete Ethereum address and
open its JSON attachment. Check a follow-up, a second chat, refresh during processing,
and restart the backend to verify expiry.

## Backend Setup

Run the following commands from the repository root unless a command says to
enter `backend/`.

For Docker, put secrets in the ignored root `.env` file. The Compose service
passes them only to the backend and detector. For a native/manual run, set the
same variables in the shell or use the locally ignored
`backend/api_keys/api_keys.py`. Never commit real credentials or place them in
frontend settings.

Install the LLM provider and terminal UI dependencies from the backend folder:

```bash
cd backend
pip install -r requirements.txt
```

The CLI starts with OpenAI. Type `change ai` to select OpenAI, Gemini, or
Claude for all LLM-backed agents in the current session. Configure a key in
the environment or as the matching constant in `backend/api_keys/api_keys.py`:

| Provider | Environment variable | `api_keys.py` constant |
| --- | --- | --- |
| OpenAI | `OPENAI_API_KEY` | `OPENAI_API_KEY` |
| Gemini | `GEMINI_API_KEY` | `GEMINI_API_KEY` |
| Claude | `ANTHROPIC_API_KEY` or `CLAUDE_API_KEY` | `CLAUDE_API_KEY` |

Values such as `"Enter key here"` are treated as unset.

## Run ChainGuard CLI

Start the interactive CLI from the `backend/` directory:

```bash
python -m src.main
```

In the interactive CLI, enter `attach "path to file.json"` to queue a UTF-8
`.txt` or `.json` file (up to 50 KB) for your next prompt. The file is sent as
untrusted reference data; JSON attachments must parse successfully.

Use development mode to print the raw BA analysis alongside plain-text
responses. Raw fetcher results are saved to JSON without being printed.
Saved context and contract-address lookup files are
reported with a confirmation and file path instead of printing their contents:

```bash
python -m src.main -dev
```

## Test Individual Fetchers

Run a fetcher with `-test` from `backend/` to enter an address, check whether
JSON is returned, and save the response in `fetchers/json_files_test/`:

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
| Contract Fetcher | Bytecode, ABI (if verified), creator, creation tx | `backend/fetchers/contract_fetcher.py` |
| Transaction History Fetcher | Recent transactions in/out | `backend/fetchers/transaction_history_fetcher.py` |
| Token Info Fetcher | Token balances and metadata held by the address | `backend/fetchers/token_info_fetcher.py` |
| Liquidity / paired-pool Fetcher | DEX pool pairing, liquidity depth, recent add/remove events | `backend/fetchers/liquidty_pairedPool_fetcher.py` |
| Tx-hash Resolver Fetcher | Given a tx hash, look up the transaction and extract the address(es) involved | `backend/fetchers/tx_hash_fetcher.py` |
| Contract Address Resolver Fetcher | Given a token name/symbol, resolve possible contract addresses (best-effort, flag ambiguous matches rather than guessing) | `backend/fetchers/contract_address_fetcher.py` |

---

# API and detector architecture

The API has two key stages:

1. Fetcher stage
   - Existing fetchers are run against the address.
   - The CLI already contains this logic in `backend/src/main.py` via `fetch_results()`.

2. Context-building stage
   - `backend/src/context_builder.py` takes the raw fetcher output and converts it into a single `AddressContext` object.
   - This normalises the data into a structure that the detector can use without needing to know the internal details of every fetcher.

The builder is important because the detector should receive consistent data, not a pile of raw fetcher results with different formats and skip/fail states.

Address lookups persist successful fetcher results under
`backend/fetchers/cache/fetcher_results/`. Cache keys include the fetcher,
address, chain, and other request arguments. Transactions and liquidity expire
after 60 seconds, contract and token information after 5 minutes, and
transaction-hash lookups after 24 hours. Failed and skipped fetches are not
cached. Each fetcher's provenance reports whether its result came from the
network or disk, along with the fetch time, age, and TTL. Delete that cache
folder to force fresh results.

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

## Address lookup summaries and follow-ups

An `address_info` lookup calls the Business Analyser to plan the request, runs
the selected fetchers, and passes the assembled JSON to the Forensic
Investigator. The investigator produces a plain-text summary and a descriptive
JSON download filename. Filenames are sanitized before use; the downloaded
JSON retains the fetched context and provenance.

Contract lookups also read `name()` and `symbol()` through Etherscan `eth_call`,
including for unverified contracts. The assembled context stores these under
`contract.token_metadata`, with address, chain ID, `latest` block tag, fetch time,
and separate success/failure statuses for each field. Standard ABI strings and
legacy bytes32 returns are supported. Wallets and delegated wallets skip these
calls; unavailable metadata does not discard the other contract results. These
values describe the contract's reported identity, not verified project ownership.

Lookup evidence is retained privately in the current chat history. Questions
such as "What are the notable transactions?" are routed by the BA using
`use_saved_lookup` and answered by the investigator from the saved data without
another fetch. Fresh lookups still run the fetchers. The investigator distinguishes
failed or skipped fetches from successful empty results. If analysis fails, the
JSON remains downloadable. Web chat history and evidence expire on backend restart.

## External detector registration

The detection algorithm is hosted outside this repository. To register it with
the BA, edit `backend/detector_config.json` and set `enabled` to
`true`, `name` to the detector name, and `endpoint` to the detector service's
HTTP endpoint.

The BA reads `backend/detector_config.json` on every request. Its task output, including
`address_info`, will contain:

```json
"selected_detector": "my_custom_scam_detector",
"detector_configured": true
```

Set `enabled` to `false` or remove `backend/detector_config.json` to return to
`null` / `false`. Invalid configuration produces an error instead of silently
reporting no detector. Registration describes setup; it does not check endpoint
availability.

In the web app, open **Settings**, edit the detector fields, then select **Save
Changes**. The Enabled toggle is only a draft until saved. Enabling the detector
does not start or install it; the service at `endpoint` must already be running
and reachable from the backend. The backend sends an HTTP `POST` with an
`AddressContext` JSON body and validates a `DetectionResult` response. Opening
the endpoint in a browser sends `GET`, so a `405 Method Not Allowed` response
can be expected; test it with a `POST` or the detector's `/docs` page.

The optional `mode`, `required_input_type`, and `is_llm_based` settings default
to `template`, `address_with_context`, and `false` for existing registrations.

### Detector configuration fields

`backend/detector_config.json` must remain valid JSON, so do not add `//` comments
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
be stored in `backend/detector_config.json`.

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

Run `python -m src.main` from `backend/`. For example, ask
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
