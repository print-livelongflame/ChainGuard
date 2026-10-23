"""Admin-only local connection and agent selection endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request

from src.auth import require_admin
from src.llm_config import (AgentSettings, AgentTokenLimits, Assignments, ProviderModels, LocalUpdate, CONFIG_LOCK, get_llm_settings,
    save_llm_settings, merge_local, test_local, check_local, public_settings)
from src.llm_provider import list_providers, provider_available

router = APIRouter(prefix="/api/settings/llm", tags=["LLM settings"], dependencies=[Depends(require_admin)])


@router.post("/agents")
def save_agent_settings(body: AgentSettings):
    try:
        with CONFIG_LOCK:
            config = get_llm_settings()
            config.agents = body
            save_llm_settings(config)
        return public_settings(config, probe=False)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/token-limits")
def save_token_limits(body: AgentTokenLimits):
    try:
        with CONFIG_LOCK:
            config = get_llm_settings()
            config.token_limits = body
            save_llm_settings(config)
        return public_settings(config, probe=False)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/models")
def save_provider_models(body: ProviderModels):
    try:
        with CONFIG_LOCK:
            config = get_llm_settings()
            config.models = body
            save_llm_settings(config)
        return public_settings(config, probe=False)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


def refresh_provider_status(app):
    config = get_llm_settings()
    labels = dict(list_providers()) | {"local": "Local Hosted LLM"}
    assigned = config.assignments.model_dump()
    app.state.provider = " · ".join(f"{label}: {labels[assigned[role]]}" for role, label in (
        ("business_analyser", "BA"), ("scam_checker", "Scam Checker"), ("forensic_investigator", "FI")))
    ba = config.assignments.business_analyser
    app.state.provider_error = None
    if ba == "local":
        if not config.local.enabled or not config.local_verified:
            app.state.provider_error = "Connect and enable the local LLM in admin settings."
    elif not provider_available(ba):
        app.state.provider_error = f"Configure the {labels[ba]} API key in admin settings."


@router.get("")
def read_settings():
    try:
        return public_settings(get_llm_settings())
    except ValueError as error:
        raise HTTPException(500, str(error)) from error


@router.post("/local/test")
def test_connection(body: LocalUpdate):
    try:
        test_local(merge_local(body, get_llm_settings().local))
        return {"connected": True, "message": "Connection and structured JSON generation succeeded."}
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/local")
def save_connection(body: LocalUpdate, request: Request):
    try:
        previous = get_llm_settings()
        local = merge_local(body, previous.local)
        if not local.enabled and "local" in previous.assignments.model_dump().values():
            raise ValueError("Choose other providers for all agents before disabling the local LLM.")
        if local.enabled:
            test_local(local)
        with CONFIG_LOCK:
            config = get_llm_settings()
            if config.local != previous.local:
                raise ValueError("Another admin changed the connection during the test. Reload and try again.")
            if not local.enabled and "local" in config.assignments.model_dump().values():
                raise ValueError("Choose other providers for all agents before disabling the local LLM.")
            config.local = local
            config.local_verified = local.enabled
            save_llm_settings(config)
        refresh_provider_status(request.app)
        return public_settings(config, probe=False)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/assignments")
def save_assignments(body: Assignments, request: Request):
    try:
        previous = get_llm_settings()
        for role, selected in body.model_dump().items():
            if selected == "local":
                if not previous.local.enabled or not previous.local_verified:
                    raise ValueError("Connect, enable and save the local LLM before selecting it.")
            elif selected != getattr(previous.assignments, role) and not provider_available(selected):
                raise ValueError(f"Configure the {selected} API key before selecting it.")
        if "local" in body.model_dump().values():
            check_local(previous.local)
        with CONFIG_LOCK:
            config = get_llm_settings()
            if config.local != previous.local or config.assignments != previous.assignments:
                raise ValueError("LLM settings changed while saving. Reload and try again.")
            config.assignments = body
            save_llm_settings(config)
        refresh_provider_status(request.app)
        return public_settings(config, probe=False)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
