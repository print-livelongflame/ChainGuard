import os
import secrets
from time import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/auth", tags=["Authentication"])

ADMIN_COOKIE = "chainguard_admin"
SESSION_SECONDS = 60 * 60  # One hour


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


def remove_expired_sessions(request: Request):
    sessions = request.app.state.admin_sessions
    current_time = time()

    for token, expires_at in list(sessions.items()):
        if expires_at <= current_time:
            sessions.pop(token, None)


def is_admin(request: Request) -> bool:
    remove_expired_sessions(request)

    token = request.cookies.get(ADMIN_COOKIE)
    return token is not None and token in request.app.state.admin_sessions


def require_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(
            status_code=403,
            detail="Admin login required.",
        )


@router.get("/me")
def current_user(request: Request):
    return {
        "role": "admin" if is_admin(request) else "user",
    }


@router.post("/login")
def login(body: LoginInput, request: Request, response: Response):
    username = os.environ.get("CHAINGUARD_ADMIN_USERNAME")
    password = os.environ.get("CHAINGUARD_ADMIN_PASSWORD")

    if not username or not password:
        raise HTTPException(
            status_code=503,
            detail="Admin login is not configured.",
        )

    username_matches = secrets.compare_digest(
        body.username.encode("utf-8"),
        username.encode("utf-8"),
    )
    password_matches = secrets.compare_digest(
        body.password.encode("utf-8"),
        password.encode("utf-8"),
    )

    if not (username_matches and password_matches):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password.",
        )

    remove_expired_sessions(request)

    # Replace this browser's previous admin session.
    previous_token = request.cookies.get(ADMIN_COOKIE)
    request.app.state.admin_sessions.pop(previous_token, None)

    token = secrets.token_urlsafe(32)
    request.app.state.admin_sessions[token] = time() + SESSION_SECONDS

    response.set_cookie(
        key=ADMIN_COOKIE,
        value=token,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        max_age=SESSION_SECONDS,
        path="/api",
    )

    return {"role": "admin"}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(ADMIN_COOKIE)
    request.app.state.admin_sessions.pop(token, None)

    response.delete_cookie(
        key=ADMIN_COOKIE,
        path="/api",
    )

    return {"role": "user"}