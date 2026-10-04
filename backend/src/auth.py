"""Local demo accounts and expiring server-side login sessions."""
import os
import secrets
from time import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
AUTH_COOKIE = "chainguard_auth"
SESSION_SECONDS = 3600


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


def get_session(request: Request):
    sessions = request.app.state.auth_sessions
    for token, session in list(sessions.items()):
        if session["expires_at"] <= time():
            sessions.pop(token, None)
    return sessions.get(request.cookies.get(AUTH_COOKIE))


def require_login(request: Request):
    session = get_session(request)
    if session is None:
        raise HTTPException(401, "Please sign in.")
    return session


def require_admin(request: Request):
    session = require_login(request)
    if session["role"] != "admin":
        raise HTTPException(403, "Admin login required.")
    return session


def view(session):
    if session is None:
        return {"authenticated": False, "role": None, "username": None}
    return {"authenticated": True, "role": session["role"], "username": session["username"]}


@router.get("/me")
def current_user(request: Request):
    return view(get_session(request))


@router.post("/login")
def login(body: LoginInput, request: Request, response: Response):
    account = None
    for role in ("admin", "user"):
        prefix = f"CHAINGUARD_{role.upper()}"
        username = os.environ.get(f"{prefix}_USERNAME", "")
        password = os.environ.get(f"{prefix}_PASSWORD", "")
        matches_name = secrets.compare_digest(body.username.encode(), username.encode())
        matches_password = secrets.compare_digest(body.password.encode(), password.encode())
        if username and password and matches_name and matches_password:
            account = {"username": username, "role": role, "expires_at": time() + SESSION_SECONDS}
            break
    if account is None:
        raise HTTPException(401, "Incorrect username or password.")
    get_session(request)
    request.app.state.auth_sessions.pop(request.cookies.get(AUTH_COOKIE), None)
    token = secrets.token_urlsafe(32)
    request.app.state.auth_sessions[token] = account
    response.set_cookie(AUTH_COOKIE, token, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https", max_age=SESSION_SECONDS, path="/api")
    return view(account)


@router.post("/logout")
def logout(request: Request, response: Response):
    request.app.state.auth_sessions.pop(request.cookies.get(AUTH_COOKIE), None)
    response.delete_cookie(AUTH_COOKIE, path="/api")
    return view(None)
