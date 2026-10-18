"""Local, single-worker web API. Run: uvicorn src.api:app --host 127.0.0.1."""
import asyncio
import hashlib
import re
import logging
import os
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.concurrency import run_in_threadpool
from src.auth import router as auth_router, require_admin, get_session

from agents.ba import is_exit_command
from src.chat_service import (
    ASSESSMENT_PREFIX,
    MAX_ATTACHMENT_BYTES,
    build_prompt,
    run_turn,
    validate_attachment,
)
from src.llm_provider import list_providers, set_progress_enabled, set_provider
from src.llm_provider import track_token_usage, use_llm_settings
from src.llm_config import get_llm_settings, settings_exist
from src.llm_settings_api import router as llm_router, refresh_provider_status
from src.main import execute_ba_task
from src.schema import DetectionResult
from src.api_key_config import (
    apply_api_key_updates,
    get_api_key_status,
    save_api_keys,
)

from src.detector_config import (DetectorConfig, get_detector_settings,save_detector_settings,)

logger = logging.getLogger(__name__)
COOKIE = "chainguard_session"


def now():
    return datetime.now(timezone.utc).isoformat()


class Attachment(BaseModel):
    id: str
    name: str
    url: str | None = None


class InputAttachment(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    content: str = Field(max_length=MAX_ATTACHMENT_BYTES)

    @model_validator(mode="after")
    def valid_file(self):
        validate_attachment(self.name, self.content)
        return self


class AnalysisResult(DetectionResult):
    source: str
    address: str | None = None


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class Message(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    role: Literal["user", "assistant"]
    text: str
    created_at: str = Field(default_factory=now)
    attachments: list[Attachment] = Field(default_factory=list)
    assessment: AnalysisResult | None = None
    lookup: dict | None = None
    token_usage: TokenUsage | None = None


class ChatView(BaseModel):
    id: str
    title: str
    created_at: str
    messages: list[Message]
    processing: bool
    error: str | None


class MessageInput(BaseModel):
    text: str = Field(default="", max_length=12000)
    attachments: list[InputAttachment] = Field(default_factory=list, max_length=1)

    @model_validator(mode="after")
    def has_message_content(self):
        if not self.text.strip() and not self.attachments:
            raise ValueError("Enter a message.")
        self.text = self.text.strip()
        return self


ApiKeyName = Literal[
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CLAUDE_API_KEY",
    "ETHERSCAN_API_KEY",
    "DETECTOR_API_KEY",
]


class ApiKeyUpdate(BaseModel):
    keys: dict[ApiKeyName, str | None] = Field(min_length=1, max_length=6)


class ApiKeyStatus(BaseModel):
    configured: dict[str, bool]
    provider: str
    configuration_error: str | None


@dataclass
class Chat:
    id: str = field(default_factory=lambda: uuid4().hex)
    title: str = "New chat"
    created_at: str = field(default_factory=now)
    messages: list[Message] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)
    files: dict[str, Path] = field(default_factory=dict)
    processing: bool = False
    error: str | None = None

    def view(self):
        return ChatView(**{key: getattr(self, key) for key in ChatView.model_fields})


def create_app():
    @asynccontextmanager
    async def lifespan(app):
        # Initialize LiteLLM on the main thread before chat workers start.
        # Its logging imports can deadlock during a first import in a worker.
        import litellm

        app.state.sessions = {}
        app.state.auth_sessions = {}
        app.state.account_chats = {}
        app.state.tasks = set()
        provider = os.environ.get("CHAINGUARD_AI_PROVIDER", "openai").strip().lower()
        labels = dict(list_providers())
        if provider not in labels:
            raise RuntimeError("CHAINGUARD_AI_PROVIDER must be openai, gemini, or claude.")
        app.state.provider_id = provider
        app.state.provider = labels[provider]
        app.state.provider_error = None
        try:
            set_provider(provider)
        except ValueError as error:
            app.state.provider_error = str(error)
        set_progress_enabled(False)
        if settings_exist():
            refresh_provider_status(app)
        with TemporaryDirectory(prefix="chainguard-web-") as directory:
            app.state.output_root = Path(directory)
            yield
            if app.state.tasks:
                await asyncio.gather(*app.state.tasks, return_exceptions=True)

    app = FastAPI(title="ChainGuard local chat", lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(llm_router)

    @app.middleware("http")
    async def browser_session(request: Request, call_next):
        session_id = request.cookies.get(COOKIE)
        fresh = session_id not in app.state.sessions
        if fresh:
            session_id = secrets.token_urlsafe(32)
            app.state.sessions[session_id] = {}
        account = get_session(request)
        if account:
            identity = (account["role"], account["username"])
            request.state.chats = app.state.account_chats.setdefault(identity, {})
        else:
            request.state.chats = app.state.sessions[session_id]
        response = await call_next(request)
        if fresh:
            response.set_cookie(COOKIE, session_id, httponly=True, samesite="strict")
        response.headers["Cache-Control"] = "no-store"
        return response

    def find_chat(request, chat_id):
        chat = request.state.chats.get(chat_id)
        if chat is None:
            raise HTTPException(404, "Chat no longer available. Start a new chat.")
        return chat

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok"}
    
    @app.get(
        "/api/settings/detector",
        response_model=DetectorConfig,
    )
    async def read_detector_settings():
        try:
            return get_detector_settings()
        except ValueError as error:
            raise HTTPException(
                status_code=500,
                detail=str(error),
            ) from error


    @app.post(
        "/api/settings/detector",
        response_model=DetectorConfig,
    )
    async def update_detector_settings(body: DetectorConfig):
        try:
            return save_detector_settings(body)
        except ValueError as error:
            raise HTTPException(
                status_code=500,
                detail=str(error),
            ) from error

    @app.get("/api/settings/api-keys", response_model=ApiKeyStatus)
    async def read_api_key_settings():
        try:
            return ApiKeyStatus(
                configured=get_api_key_status(),
                provider=app.state.provider,
                configuration_error=app.state.provider_error,
            )
        except ValueError as error:
            raise HTTPException(status_code=500, detail=str(error)) from error

    @app.post("/api/settings/api-keys", response_model=ApiKeyStatus)
    async def update_api_key_settings(body: ApiKeyUpdate, request: Request):
        admin_only_keys = {
            "OPENAI_API_KEY", "GEMINI_API_KEY", "CLAUDE_API_KEY", "ANTHROPIC_API_KEY",
        }
        if admin_only_keys.intersection(body.keys):
            require_admin(request)
        try:
            save_api_keys(body.keys)
            apply_api_key_updates(body.keys)
            try:
                app.state.provider = set_provider(app.state.provider_id)
                app.state.provider_error = None
            except ValueError as error:
                app.state.provider_error = str(error)
            if settings_exist():
                refresh_provider_status(app)
            return ApiKeyStatus(
                configured=get_api_key_status(),
                provider=app.state.provider,
                configuration_error=app.state.provider_error,
            )
        except ValueError as error:
            raise HTTPException(status_code=500, detail=str(error)) from error

    @app.get("/api/chats")
    async def list_chats(request: Request):
        return {
            "provider": app.state.provider,
            "configuration_error": app.state.provider_error,
            "chats": [chat.view() for chat in reversed(list(request.state.chats.values()))],
        }

    @app.post("/api/chats", response_model=ChatView, status_code=201)
    async def create_chat(request: Request):
        chat = Chat()
        request.state.chats[chat.id] = chat
        return chat.view()

    @app.get("/api/chats/{chat_id}", response_model=ChatView)
    async def get_chat(chat_id: str, request: Request):
        return find_chat(request, chat_id).view()

    def execute_turn(chat, prompt, attachments=()):
        with track_token_usage() as token_usage:
            return execute_turn_with_usage(chat, prompt, attachments, token_usage)

    def execute_turn_with_usage(chat, prompt, attachments, token_usage):
        messages = []
        files = {}
        history = list(chat.history)
        seen_files = set()
        pending_assessment = None
        pending_lookup = None
        usage_checkpoint = 0

        def capture_lookup(evidence, task, follow_up):
            nonlocal pending_lookup, pending_assessment
            if len(evidence) != 1:
                return
            context = evidence[0]
            wants_transactions = task.request_type == "address_info" and (
                "tx_history" in task.requested_fields or bool(
                    re.search(r"\btransactions?\b", prompt, re.IGNORECASE)))
            if follow_up and context.get("detector_assessment"):
                pending_assessment = AnalysisResult.model_validate(context["detector_assessment"])
            if wants_transactions or (follow_up and pending_assessment):
                pending_lookup = {
                    "kind": "transactions" if wants_transactions else "evidence",
                    "address": context.get("address"),
                    "chain": context.get("chain", "unknown"),
                    "queried_at": context.get("queried_at"),
                    "transactions": context.get("tx_history") or [],
                    "provenance": next((value for value in context.get("fetcher_provenance", {}).values()
                                        if "tx_history" in value.get("fields", [])), {}),
                }

        def capture_assessment(result, source, address):
            nonlocal pending_assessment
            pending_assessment = AnalysisResult(
                **result.model_dump(include=set(DetectionResult.model_fields)),
                source=source, address=address,
            )
            history.append({"role": "assistant", "content":
                            ASSESSMENT_PREFIX + pending_assessment.model_dump_json()})

        def respond(text, label, output):
            nonlocal pending_assessment, pending_lookup, usage_checkpoint
            attachments = []
            if output:
                text = text.replace(str(output), "the attached JSON result")
            if output and output.is_file():
                content = output.read_bytes()
                version = (output, hashlib.sha256(content).digest())
                if version not in seen_files:
                    seen_files.add(version)
                    file_id = uuid4().hex
                    # Resolvers and context builders can write the same task path.
                    # Download links must keep the exact result they accompanied.
                    snapshot = output.with_name(f"{file_id}.json")
                    snapshot.write_bytes(content)
                    files[file_id] = snapshot
                    attachments.append(Attachment(
                        id=file_id, name=output.name,
                        url=f"/api/chats/{chat.id}/files/{file_id}",
                    ))
            messages.append(Message(
                role="assistant", text=f"{label}\n{text}" if label else text,
                attachments=attachments, assessment=pending_assessment, lookup=pending_lookup,
                token_usage=token_usage.since(usage_checkpoint),
            ))
            usage_checkpoint = token_usage.checkpoint()
            pending_assessment = None
            pending_lookup = None
            return text

        if prompt.casefold() == "change ai":
            respond("The web app uses the provider configured on the server.", None, None)
        elif is_exit_command(prompt):
            respond("Goodbye! You can start a new chat or continue here whenever you like.", None, None)
        else:
            run_turn(
                prompt, history,
                execute=lambda task, reply, output: execute_ba_task(
                    task, reply, output, diagnostics=False, on_assessment=capture_assessment),
                respond=respond, output_root=app.state.output_root / chat.id,
                on_lookup=capture_lookup,
                attachments=attachments,
            )
        if not messages:
            respond("No answer was produced. Please rephrase your request.", None, None)
        return messages, files, history

    async def finish_turn(chat, prompt, attachments=()):
        try:
            with use_llm_settings(get_llm_settings()):
                messages, files, history = await run_in_threadpool(
                    execute_turn, chat, prompt, attachments
                )
            chat.messages.extend(messages)
            chat.files.update(files)
            chat.history = history
        except Exception as error:
            logger.exception("Chat turn failed")
            if "response was incomplete (token limit)" in str(error).casefold():
                chat.error = (
                    "The AI response hit its output-token limit before the analysis "
                    "could finish. In Settings > Token Limits, increase or clear "
                    "the Business Analyser limit, or shorten your request, then try again."
                )
            else:
                chat.error = "Unable to complete this request. Check the backend configuration and try again."
            chat.messages.append(Message(role="assistant", text=chat.error))
        finally:
            chat.processing = False

    @app.post("/api/chats/{chat_id}/messages", response_model=ChatView)
    async def send_message(chat_id: str, body: MessageInput, request: Request):
        chat = find_chat(request, chat_id)
        if chat.processing:
            raise HTTPException(409, "This chat is still processing a message.")
        if app.state.provider_error:
            raise HTTPException(503, app.state.provider_error)
        chat.processing = True
        chat.error = None
        attachments = [validate_attachment(item.name, item.content) for item in body.attachments]
        default_prompt = "Please analyze the attached file."
        if attachments and attachments[0]["name"].casefold().endswith(".json"):
            default_prompt = (
                "Please investigate the blockchain target in the attached JSON "
                "for a potential scam."
            )
        prompt = build_prompt(
            body.text or default_prompt,
            attachments,
        )
        if not chat.messages:
            chat.title = (body.text or attachments[0]["name"])[:60]
        chat.messages.append(Message(
            role="user", text=body.text,
            attachments=[Attachment(id=uuid4().hex, name=item["name"]) for item in attachments],
        ))
        task = asyncio.create_task(finish_turn(chat, prompt, attachments))
        app.state.tasks.add(task)
        task.add_done_callback(app.state.tasks.discard)
        # A refresh/disconnect must not cancel an accepted turn.
        await asyncio.shield(task)
        return chat.view()

    @app.get("/api/chats/{chat_id}/files/{file_id}")
    async def download(chat_id: str, file_id: str, request: Request):
        chat = find_chat(request, chat_id)
        path = chat.files.get(file_id)
        if path is None or not path.is_file():
            raise HTTPException(404, "Result file not found.")
        name = next(
            item.name for message in chat.messages for item in message.attachments
            if item.id == file_id
        )
        return FileResponse(path, media_type="application/json", filename=name)

    return app


app = create_app()
