from __future__ import annotations

from typing import Any

import httpx
from fastapi import Request, Response

from app.core.config import settings
from app.core.errors import AppError


def map_user(user: Any) -> dict[str, Any]:
    metadata = getattr(user, "user_metadata", None) or {}
    username = metadata.get("username") or metadata.get("full_name")
    return {
        "id": getattr(user, "id", None),
        "email": getattr(user, "email", None),
        "username": username,
        "fullName": metadata.get("full_name"),
    }


import os

IS_PRODUCTION = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

def set_auth_cookie(response: Response, name: str, value: str, max_age: int = 3600):
    response.set_cookie(
        key=name,
        value=value,
        httponly=True,
        secure=IS_PRODUCTION,          # True on HTTPS (Render), False on localhost
        samesite="none" if IS_PRODUCTION else "lax",
        # SameSite=None is REQUIRED for cross-origin cookie sending on Edge and Safari
        # It MUST be paired with Secure=True (only works on HTTPS)
        max_age=max_age,
        path="/",
    )


def set_auth_cookies(response: Response, access_token: str, refresh_token: str, expires_in: int | None):
    access_ttl = expires_in if isinstance(expires_in, int) and expires_in > 0 else 3600
    refresh_ttl = 60 * 60 * 24 * 7

    set_auth_cookie(response, settings.access_token_cookie_name, access_token, max_age=access_ttl)
    set_auth_cookie(response, settings.refresh_token_cookie_name, refresh_token, max_age=refresh_ttl)


def clear_auth_cookies(response: Response):
    set_auth_cookie(response, settings.access_token_cookie_name, "", max_age=0)
    set_auth_cookie(response, settings.refresh_token_cookie_name, "", max_age=0)


def extract_access_token(request: Request, authorization: str | None) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1]

    token = request.cookies.get(settings.access_token_cookie_name)
    return token if token else None


async def revoke_supabase_session(access_token: str):
    async with httpx.AsyncClient(timeout=20) as client:
        logout_response = await client.post(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/logout",
            headers={
                "apikey": settings.supabase_service_role_key,
                "Authorization": f"Bearer {access_token}",
            },
        )
        if logout_response.status_code >= 400:
            raise AppError("Failed to sign out from Supabase", logout_response.status_code, logout_response.text)
