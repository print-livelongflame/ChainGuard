# ChainGuard Frontend

React + TypeScript + Vite chat interface, styled with the supplied ChainGuard mockups.

Start the API from `backend/`:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000 --workers 1
```

Then run from this directory:

```powershell
npm.cmd install
npm.cmd run dev
```

Use the local URL printed by Vite. `/api` requests are proxied to the Python server
on port 8000. The development proxy provides the same origin for HTTP-only session
cookies, chat requests, and JSON downloads. `vite preview` only previews static
assets; use the development server for this local integration.

The server keeps chat history until restart. The browser stores only the selected
chat ID. Never add AI-provider keys to the frontend. See the [root README](../README.md)
for provider setup, API details, and lifecycle behavior.

Validation: `npm.cmd run build` and `npm.cmd run lint`.
