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


def set_auth_cookies(response: Response, access_token: str, refresh_token: str, expires_in: int | None):
    access_ttl = expires_in if isinstance(expires_in, int) and expires_in > 0 else 3600
    refresh_ttl = 60 * 60 * 24 * 7

    cookie_kwargs = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "none" if settings.cookie_secure else "lax",
        "domain": settings.cookie_domain,
        "path": "/",
    }

    response.set_cookie(settings.access_token_cookie_name, access_token, max_age=access_ttl, **cookie_kwargs)
    response.set_cookie(settings.refresh_token_cookie_name, refresh_token, max_age=refresh_ttl, **cookie_kwargs)


def clear_auth_cookies(response: Response):
    cookie_kwargs = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "none" if settings.cookie_secure else "lax",
        "domain": settings.cookie_domain,
        "path": "/",
    }
    response.set_cookie(settings.access_token_cookie_name, "", max_age=0, **cookie_kwargs)
    response.set_cookie(settings.refresh_token_cookie_name, "", max_age=0, **cookie_kwargs)


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
