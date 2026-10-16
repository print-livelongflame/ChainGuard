# ChainGuard

ChainGuard is a local web application for asking blockchain questions, looking up Ethereum addresses, and investigating possible scams. It combines blockchain data with AI explanations and can optionally send evidence to your own external detector. Findings depend on the available evidence and model; they are not guarantees that a token is safe or fraudulent.

## Choose your setup

1. **[Start the main app](#1-start-the-main-app)** with a cloud AI provider. This covers the browser interface, backend, login, and keys.
2. **[Add the local LLM template](#2-use-the-local-llm-template)** to run the AI model on your computer instead of using a cloud provider.
3. **[Connect the external detector template](#3-connect-the-external-detector-template)** to use your own detection algorithm.

The two templates serve different purposes and can be used together. A **local LLM** (large language model) generates the agents' answers. An **external detector** accepts an address and evidence and returns a structured risk assessment.

A few terms used below:

| Term | Meaning |
| --- | --- |
| Frontend | The web interface you open in your browser. |
| Backend | The Python service that handles chats, calls AI providers, and retrieves blockchain data. |
| API | An interface through which programs send requests to one another. |
| API key | A secret issued by a service to authorize requests. Obtain your own keys from the providers you use. |
| Endpoint / base URL | A service's network address. Use the exact path shown in each guide. |
| Docker Compose | A tool that builds and starts the app's services in isolated containers with one command. |

Commands below use Windows PowerShell. Run each block from the folder specified. On macOS/Linux, use `cp` instead of `Copy-Item`, and `npm` instead of `npm.cmd`. Paths such as `../ChainGuard-detector-template` mean a folder beside ChainGuard.

## 1. Start the main app

### Option A: Docker (recommended)

Install Git and Docker Desktop, start Docker Desktop, and wait for its engine to run. On Windows, use Linux containers. Linux users can use Docker Engine with the Compose plugin. Python and Node.js run inside Docker, so separate installations are unnecessary for this option.

#### Download the repositories

Open a terminal in the folder where you want to keep the project:

```powershell
git clone https://github.com/print-livelongflame/ChainGuard.git
git clone https://github.com/Mossata/ChainGuard-detector-template.git
cd ChainGuard
Copy-Item .env.example .env
```

If you already have these repositories, use the existing copies. Keep this layout:

```text
ProjectFiles/
  ChainGuard/
  ChainGuard-detector-template/
  ChainGuard-localLLM-template/   (see guide 2 for installation + setup)
```

The supplied Compose file starts the frontend, backend, **and detector service**. It therefore requires the detector repository even if you later disable detector use in Settings. Its initial algorithm is a stub, not a working scam detector.

#### Configure initial values

Open the new `ChainGuard/.env` file in a text editor. This is a local configuration file, not a terminal command. For the default OpenAI setup, fill in:

```dotenv
DETECTOR_PATH=../ChainGuard-detector-template
CHAINGUARD_AI_PROVIDER=openai
OPENAI_API_KEY=replace-with-your-openai-api-key
ETHERSCAN_API_KEY=replace-with-your-etherscan-api-key
```

Replace the example key values with real keys. Keep the remaining entries from `.env.example`; unused keys can stay empty.

| Value | When you need it |
| --- | --- |
| `CHAINGUARD_AI_PROVIDER` | Initial cloud provider: `openai`, `gemini`, or `claude`. Defaults to OpenAI. |
| `OPENAI_API_KEY` | When using OpenAI. |
| `GEMINI_API_KEY` | When using Gemini. |
| `ANTHROPIC_API_KEY` or `CLAUDE_API_KEY` | When using Claude; configure one of these. |
| `ETHERSCAN_API_KEY` | For Ethereum data lookups. A general blockchain question can work without it. |
| `DETECTOR_PATH` | Path to the detector repository, relative to ChainGuard. Keep the default for the layout above. |
| `DETECTOR_API_KEY` | Optional shared secret for detector authentication; leave empty for initial setup. |

You can leave the keys empty and enter them in the web settings after startup. Chat needs a configured provider before it can answer. If you intend to use only a local model, skip the cloud key and complete guide 2 before sending a message.

#### Start frontend and backend

From `ChainGuard/`:

```powershell
docker compose up -d --build
docker compose ps
```

The first run downloads dependencies and builds the services. `-d` keeps them running after the terminal closes. Wait for the backend and detector to become healthy and the frontend to start.

Open **http://localhost:5173**. The backend health check is **http://localhost:8000/health** and its interactive API documentation is **http://localhost:8000/docs**. A healthy backend confirms the service is running, not that your keys or model are valid.

### Option B: Run frontend and backend without Docker

Use Python **3.12** and Node.js **22.12 or newer in the Node 22 series** (the Docker/CI setup uses Node 22). Install Git if you need to clone the repository. This option does not require either template for the main app.

In a terminal in `ChainGuard/`, create an isolated Python environment and start the backend:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt
$env:CHAINGUARD_ADMIN_USERNAME = "admin"
$env:CHAINGUARD_ADMIN_PASSWORD = "ChainGuard123!"
$env:CHAINGUARD_USER_USERNAME = "user"
$env:CHAINGUARD_USER_PASSWORD = "ChainGuardUser123!"
$env:CHAINGUARD_AI_PROVIDER = "openai"
cd backend
..\.venv\Scripts\python -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --workers 1
```

These account values are local demo credentials. You can choose different values, then use those when signing in. Set them in the backend terminal each time you start it. On macOS/Linux, use `.venv/bin/python` (or `../.venv/bin/python` from `backend/`) and `export NAME='value'` instead of PowerShell's `$env:NAME = "value"`.

Leave this terminal running. Open a **second terminal** in `ChainGuard/`:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open **http://localhost:5173**, or the URL Vite prints if that port is occupied. Keep both terminals running. The frontend forwards `/api` requests to the backend on port 8000; use the frontend URL for the app.

For this setup, enter API keys through Settings as described next, or set the variables in the table above in the backend terminal before starting it. **The root `.env` file is used by Docker Compose; the native backend does not automatically load it.**

### Sign in and finish configuration (both options)

The supplied Docker configuration uses these accounts; native setup uses the values you set above:

| Role | Username | Password |
| --- | --- | --- |
| Administrator | `admin` | `ChainGuard123!` |
| User | `user` | `ChainGuardUser123!` |

Sign in as **admin** for initial setup. The admin-only settings affect all users. Docker's account values are defined directly in `docker-compose.yml`; changing them requires editing its backend environment entries and recreating the backend. This configuration is for local use on a trusted machine.

1. Open **Settings > AI Configuration**. If you did not supply a cloud key earlier, enter the key for your chosen provider and click its **Save** button.
2. In the agent provider controls on that page, select the configured provider for the Business Analyser, Scam Checker, and Forensic Investigator, then click **Save Agent Providers**. These are the three AI roles explained at the end of this README. You may select different providers for each role if their keys are configured.
3. Open **Settings > API Wrappers**. Enter your **Etherscan API Key** and click **Save** if you did not set it earlier. A configured badge indicates a key is stored; it does not verify that the service accepts it.
4. For the main app's built-in AI assessment, open **Settings > External Detector**, turn **Enabled** off, click **Save Changes**, then **Confirm Change**. Docker enables its detector by default when there is no saved configuration; disabling it prevents the template stub from handling scam checks. Native setup defaults to disabled unless a saved configuration says otherwise.

Saved agent assignments take precedence over the initial `CHAINGUARD_AI_PROVIDER` value. Changes apply to future messages; a running response keeps its original AI settings.

### Try your first chat

Return to chat and ask **"What is a smart contract?"**. A response confirms that your selected AI provider can answer. Next, try:

```text
Look up the Ethereum contract at 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 and summarize the available evidence.
```

This also exercises blockchain fetching. Inspect the explanation and JSON download, including failed or skipped data sources. You can then ask a follow-up about the saved evidence or request a scam assessment of an address.

Use **New Chat** for a separate conversation. Enter sends; Shift+Enter adds a line. The paperclip attaches one UTF-8 `.txt` or valid `.json` file, up to 10 MB. Replace example address placeholders with a full Ethereum address. ChainGuard asks for clarification when an attachment identifies multiple possible targets.

### Stop, restart, and retain settings

For Docker, run from `ChainGuard/`:

```powershell
docker compose down
docker compose up -d
docker compose up -d --build
```

These commands respectively stop the stack, start it again, and rebuild/start it after source or dependency changes. For a native run, press Ctrl+C in each terminal, then repeat the startup commands with the existing environment and installed dependencies.

Chat transcripts, saved lookup evidence, and login sessions are held in backend memory and are lost on backend restart. Login sessions expire after one hour. JSON result downloads are temporary and removed on normal shutdown.

Docker stores detector and AI connection settings in the `chainguard_data` volume (`/data/detector_config.json` and `/data/llm_config.json`). Native runs use `backend/detector_config.json` and `backend/llm_config.json` unless their configuration path variables override them. Saved API keys live in the ignored **`backend/api_keys/api_keys.py`**, also mounted into Docker. These are plaintext secrets on disk; keep that file and `.env` private and out of commits. Nonempty environment keys take precedence at startup, so update/remove them there too when changing saved keys. Never put secrets in frontend environment variables.

## 2. Use the local LLM template

Complete the main app setup first; a cloud key is optional for this guide. This template runs **Ollama**, which loads a downloaded model, and a hosting service that translates ChainGuard's requests into Ollama requests. Blockchain lookups still use external services such as Etherscan.

### Start the model server and download a model

From the parent folder containing `ChainGuard/`:

```powershell
git clone https://github.com/Mossata/ChainGuard-localLLM-template.git
cd ChainGuard-localLLM-template
docker compose up -d --build
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama list
```

Skip cloning if the folder already exists. Wait for the model download to finish and confirm its exact name appears in the list. This example can run on a CPU; allow disk space for the model plus memory for Docker and inference. CPU generation can be slow, and this small model may struggle with ChainGuard's structured answers. See the [hosting template README](../ChainGuard-localLLM-template/README.md) for optional NVIDIA GPU configuration and server settings.

Open **http://localhost:9010/ready**. With default settings it should report `"status":"ready"` and list the model. Readiness checks availability; ChainGuard's connection test also checks generation.

### Connect Docker networks

If ChainGuard runs in Docker, start the template **first**, then run from `ChainGuard/`:

```powershell
docker compose -f docker-compose.yml -f ../ChainGuard-localLLM-template/chainguard-network.yaml up -d --build
```

The extra file joins the backend to the model server's Docker network. Use these same two `-f` options for subsequent ChainGuard Compose commands, including `ps`, `logs`, `up`, and `down`. Keep the model template running. If ChainGuard runs natively, skip this network step.

### Configure ChainGuard

Sign in as admin and open **Settings > Local LLM Connection**:

| Field | Value for the setup above |
| --- | --- |
| Connection name | `My local Llama` (any descriptive name) |
| API base URL | `http://chainguard-local-llm:9010/v1` for Docker ChainGuard; `http://localhost:9010/v1` for native ChainGuard |
| Model name | `llama3.2:3b` (must match the installed name) |
| Optional API key | Empty with the template defaults |
| Timeout (seconds) | `300` to start with |

Click **Test Connection**, turn on **Enable local LLM**, and click **Save Connection**. Saving an enabled connection verifies model listing and a small structured JSON response. A failed verification leaves the previous saved settings intact.

Then open **Settings > AI Configuration**, select **Local Hosted LLM** for all three agents, and click **Save Agent Providers**. To keep some agents on cloud services, configure their keys and leave those roles on their cloud providers. Starting the model server or testing the connection alone does not change the agents.

Try the general question from guide 1. Disable the external detector to exercise the local Scam Checker; an enabled external detector handles that assessment instead. Local model failures do not automatically fall back to a cloud provider.

For an optional model-server password, copy the template's `.env.example` to `.env`, set `LLM_API_KEY`, and reapply `docker compose up -d` in the template folder. Enter the same secret in ChainGuard's **Optional API key** field. Its `/ready` endpoint then needs bearer authentication; `/health` remains public. This key is separate from cloud and detector keys.

If your model server runs directly on the host while ChainGuard runs in Docker, use `http://host.docker.internal:9010/v1` and ensure the server accepts Docker connections. Inside a container, `localhost` refers to that container itself.

Stop the hosting stack with `docker compose down` from its own folder. Downloaded models persist in its volume. **Adding `-v` to `down` deletes that stack's saved volume data**; this also applies to ChainGuard's saved settings volume.

## 3. Connect the external detector template

An external detector is a separate HTTP service implementing your algorithm. ChainGuard sends it an address, optionally with fetched evidence, and validates the result. It does not replace the AI provider used to understand questions and explain evidence.

### Start and verify the service

With guide 1's Docker setup, the detector is already running from `ChainGuard-detector-template/`. Check **http://localhost:9000/health** and open **http://localhost:9000/docs**.

For a native setup, open a separate terminal in `ChainGuard-detector-template/`:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

Keep this terminal running. On macOS/Linux, use `.venv/bin/python`. The template does not automatically load `.env` files for native runs; set any needed variables in this terminal before starting it.

Test the interface from another terminal in the template folder:

```powershell
curl.exe -X POST http://127.0.0.1:9000/detect -H "Content-Type: application/json" --data-binary "@examples/context.json"
```

Use `curl` on macOS/Linux. The unmodified stub returns **`insufficient_evidence` with confidence `0.0`**. This confirms the interface works; it has not assessed scam risk. `/detect` requires POST; opening it directly in a browser sends GET and can return 405.

### Add your algorithm

Implement `detect_custom()` in the template's `detector.py`, mapping your algorithm's output to `DetectionResult`. Add dependencies to its `requirements.txt`. For an illustrative demonstration, the template also includes `examples/heuristic.py`; follow its [implementation guide](../ChainGuard-detector-template/README.md#implement-your-detector). That example is not a validated detection model.

For Docker ChainGuard, apply code edits from `ChainGuard/` with:

```powershell
docker compose restart detector
```

The repository is mounted at `/app` in the detector container; Python code is loaded at startup. After dependency changes, use `docker compose up -d --build detector`. If using guide 2's shared network, include both `-f` options here too. For native use, stop and restart `python app.py`, reinstalling requirements when changed.

### Register it in ChainGuard

As admin, open **Settings > External Detector**:

| Field | Value |
| --- | --- |
| Enabled | On |
| Name | A descriptive name, such as `My template detector` |
| Endpoint | `http://detector:9000/detect` when using ChainGuard's Compose detector service |
| Mode | `template` |
| Required Input Type | `address_with_context` for the template with fetched blockchain evidence |
| LLM Based | Off for a normal custom algorithm |

For a native backend and detector on the same computer, use **`http://127.0.0.1:9000/detect`**. For a Docker backend reaching a detector running on the host, use **`http://host.docker.internal:9000/detect`** and configure the detector to accept connections from Docker. For a remote deployment, use its reachable HTTPS `/detect` URL.

Click **Save Changes**, then **Confirm Change**. Saving records configuration; it does not start the service or test connectivity. Ask ChainGuard to assess a complete Ethereum address and check both backend/detector logs if the call fails. An unchanged stub will still report insufficient evidence.

Use `required_input_type: address` only when your implementation does its own lookups. Set **LLM Based** on only when the detector supplies its own LLM explanation; the template's separate LLM adapter instructions explain that setup. Leave **Mode** on `template`: generic response mapping is not implemented.

For optional authentication, Docker's root `.env` `DETECTOR_API_KEY` is passed to both services. After changing it, recreate them with `docker compose up -d`. For native runs, set the same `DETECTOR_API_KEY` in both backend and detector terminals before startup (or save the caller's key under **Settings > API Wrappers**). Requests use the `X-API-Key` header. Do not store secrets in detector registration JSON.

To return to ChainGuard's AI Scam Checker, disable the external detector and save/confirm the change. Stopping the detector service alone leaves it configured and produces request errors.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Docker cannot start | Start Docker Desktop and wait for the engine; on Windows select Linux containers. |
| Missing detector directory / Dockerfile | Clone the detector beside ChainGuard or correct `DETECTOR_PATH` in `.env`. Compose needs the whole template repository. |
| Port already in use | Stop the conflicting process. Defaults are 5173 (frontend), 8000 (backend), 9000 (detector), and 9010 (local model hosting). |
| Native login fails | Set the account variables in the terminal that starts the backend; the root `.env` is not loaded automatically. |
| Admin controls unavailable | Sign in as admin, rather than the user account. |
| Provider unavailable / key missing | Save the selected provider's key and check all three agent assignments. For local AI, enable/save the connection first. |
| Lookup data missing | Check the Etherscan key and fetcher provenance; some data may be unavailable for the address. |
| Local model cannot connect | Start its stack first, download the exact model name, apply the shared network file, and use the URL for your backend's location. |
| Local generation times out / invalid JSON | Try a more capable model or increase timeouts in both ChainGuard and the hosting template. Connection success does not guarantee every analysis will work. |
| Detector unavailable / 401 | Check the backend-visible endpoint, running service, and matching detector keys. |
| Detector always returns insufficient evidence | Replace the template stub with your implementation. |
| Chats disappear after restart | Chat storage is in memory; download any results you need to retain. |

For Docker logs, run `docker compose logs --tail 100 backend detector frontend` from `ChainGuard/`; include guide 2's two `-f` options when using its network setup. For native runs, read the backend and frontend terminal output.

## Testing and developer tools

From `ChainGuard/`, using the Python environment created in the native guide:

```powershell
.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
cd backend
..\.venv\Scripts\python -m pytest tests -q
..\.venv\Scripts\python -m pytest --cov=src --cov=detector_integration --cov=fetchers --cov-report=term-missing
```

The normal backend suite uses mocks and does not need paid API calls. It covers chat/API behavior, role access, attachments, fetchers, caching, model configuration, and detector integration. Frontend checks, from `ChainGuard/frontend/`:

```powershell
npm.cmd ci
npm.cmd run lint
npm.cmd run build
```

GitHub Actions runs backend tests and frontend lint/build for matching application changes. **Actions > Manual Docker integration test > Run workflow** separately starts the full stack and checks frontend/service health and a backend-to-detector request. It does not test a real AI response.

An optional live token benchmark is available from `backend/` with configured cloud keys:

```powershell
$env:CHAINGUARD_RUN_LLM_TOKEN_BENCHMARK = "1"
..\.venv\Scripts\python -m pytest -s -q tests/test_llm_token_usage.py
```

It makes real, potentially billable calls (three per included cloud provider). Add `--exclude=gemini,openai`, for example, to exclude providers. Remove the opt-in variable afterwards with `Remove-Item Env:CHAINGUARD_RUN_LLM_TOKEN_BENCHMARK`. Ordinary test runs skip the benchmark unless opted in.

The development CLI shares the chat workflow. From `backend/`, run `..\.venv\Scripts\python -m src.main` (add `-dev` for diagnostics). Use `change ai` for its cloud-provider menu and `attach "path to file.json"` to queue an attachment. The CLI provider menu is separate from web agent assignments. Individual fetcher modules support their existing `-test` commands, for example `..\.venv\Scripts\python -m fetchers.contract_fetcher -test`; these can call live data services.

For a manual app check, test a general question, an address lookup and JSON download, a saved-evidence follow-up, a second chat, and refresh during a pending response. Test both the configured detector path and the disabled-detector AI path when changing integrations.

## Architecture

```text
Browser frontend (React/Vite, :5173)
  -> /api proxy -> Python backend (FastAPI, :8000)
      -> Business Analyser: interpret question and plan work
      -> Ethereum fetchers -> AddressContext (evidence + source status)
      -> Address lookup: Forensic Investigator explains evidence
      -> Scam check:
           detector disabled -> Scam Checker assesses evidence
           detector enabled  -> external POST /detect (:9000 by default)
                                -> Forensic Investigator explains non-LLM results
                                -> LLM detectors supply their own explanation
      -> Chat response + downloadable context JSON

Each AI agent -> configured cloud provider OR local model host (:9010) -> Ollama
```

| Location | Responsibility |
| --- | --- |
| `frontend/` | Chat, login, settings, and downloads. |
| `backend/src/api.py`, `auth.py`, `llm_settings_api.py` | Web API, local login sessions, and AI configuration endpoints. |
| `backend/src/chat_service.py`, `main.py` | Shared web/CLI workflow and fetcher execution. |
| `backend/src/context_builder.py`, `schema.py` | Assemble and validate shared evidence structures. |
| `backend/fetchers/` | Contract/identity, transaction history, token, liquidity, and address/transaction resolution data. |
| `backend/detector_integration/` | External detector HTTP client and result handling. |
| Separate template repositories | Independently hosted detector algorithm and local model server. |

The **Business Analyser (BA)** routes requests and answers general questions. The **Scam Checker (SCH)** provides the built-in AI risk assessment when no detector is enabled. The **Forensic Investigator (FI)** summarizes fetched or saved evidence and explains non-LLM detector results. Follow-ups can reuse evidence from the current chat instead of fetching again.

`AddressContext` contains the address/chain, contract, `tx_history`, `tokens`, liquidity, timestamp, and fetcher provenance. Missing or failed fetches remain distinguishable from successful empty results. A detector returns `DetectionResult`: `label` (`scam`, `not_scam`, or `insufficient_evidence`), `risk_type`, `confidence` (0–1), structured `evidence`, and optional `explanation`. Failures and invalid results produce errors rather than safe verdicts.

The backend exposes chats/messages/downloads under `/api/chats`, login under `/api/auth`, and configuration under `/api/settings`; see `/docs` for the current request schemas. One turn runs at a time per chat. An accepted turn continues after browser disconnection, so refresh to recover its result rather than immediately resending.

Run the backend with **one worker** because chat and login stores are in memory. The supplied Docker ports bind to localhost. This is a local development/demo deployment with fixed demo accounts; the frontend's admin controls do not make every backend endpoint admin-protected. Public hosting requires a separate authentication, authorization, and deployment review.
