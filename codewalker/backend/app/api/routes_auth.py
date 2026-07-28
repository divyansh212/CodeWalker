import secrets
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from app.auth.github_oauth import (
    build_authorize_url,
    exchange_code_for_token,
    get_github_user,
    create_session_jwt,
)
from app.config import get_settings

router = APIRouter(prefix="/auth/github", tags=["auth"])


@router.get("/login")
async def login():
    state = secrets.token_urlsafe(16)
    return RedirectResponse(build_authorize_url(state))


@router.get("/callback")
async def callback(code: str, state: Optional[str] = None):
    settings = get_settings()
    try:
        access_token = await exchange_code_for_token(code)
        user = await get_github_user(access_token)
    except Exception:
        raise HTTPException(status_code=400, detail="GitHub OAuth exchange failed")

    session_token = create_session_jwt(user["login"], access_token)
    return RedirectResponse(f"{settings.frontend_url}/dashboard?token={session_token}")
