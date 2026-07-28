from typing import Optional
from fastapi import Header, HTTPException
from app.auth.github_oauth import decode_session_jwt


async def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[len("Bearer "):]
    try:
        payload = decode_session_jwt(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return payload
