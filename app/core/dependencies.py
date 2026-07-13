from __future__ import annotations

from typing import Any

from fastapi import Header, Request
from pydantic import BaseModel

from app.core.errors import AppError
from app.core.security import extract_access_token
from app.core.supabase import supabase_admin


class AuthContext(BaseModel):
    access_token: str
    user: dict[str, Any]


async def require_auth(request: Request, authorization: str | None = Header(default=None)) -> AuthContext:
    token = extract_access_token(request, authorization)
    if not token:
        raise AppError("Access token is required", 401)

    try:
        user_response = supabase_admin.auth.get_user(token)
    except Exception as exc:
        raise AppError("Unauthorized", 401, str(exc)) from exc

    user = getattr(user_response, "user", None)
    if not user:
        raise AppError("User not found", 401)

    return AuthContext(
        access_token=token,
        user={
            "id": getattr(user, "id", None),
            "email": getattr(user, "email", None),
            "user_metadata": getattr(user, "user_metadata", {}) or {},
        },
    )
