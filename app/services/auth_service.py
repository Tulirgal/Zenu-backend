from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import Request, Response

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import clear_auth_cookies, extract_access_token, map_user, revoke_supabase_session, set_auth_cookies
from app.core.supabase import app_db, supabase_admin, supabase_anon
from app.schemas import ForgotPasswordInput, RefreshInput, ResetPasswordInput, SignInInput, SignUpInput
from app.services.smtp_service import send_password_reset_email


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _get_reset_base_url() -> str:
    if settings.reset_password_url_base:
        return settings.reset_password_url_base.rstrip("/")

    if settings.frontend_origins:
        return settings.frontend_origins[0]

    if settings.frontend_url:
        return settings.frontend_url.split(",")[0].strip().rstrip("/")

    return "http://localhost:3000"


def _find_user_by_email(email: str):
    page = 1
    per_page = 200

    while True:
        users = supabase_admin.auth.admin.list_users(page=page, per_page=per_page)
        if not users:
            return None

        for user in users:
            user_email = (getattr(user, "email", None) or "").lower()
            if user_email == email.lower():
                return user

        if len(users) < per_page:
            return None

        page += 1


def sign_up(payload: SignUpInput, response: Response):
    try:
        supabase_admin.auth.admin.create_user(
            {
                "email": payload.email,
                "password": payload.password,
                "email_confirm": True,
                "user_metadata": {
                    "full_name": payload.fullName,
                    "username": payload.username,
                },
            }
        )
    except Exception as exc:
        raise AppError("Failed to create user", 400, str(exc)) from exc

    try:
        auth_result = supabase_anon.auth.sign_in_with_password({"email": payload.email, "password": payload.password})
    except Exception as exc:
        raise AppError("Failed to create session after sign-up", 500, str(exc)) from exc

    session = getattr(auth_result, "session", None)
    user = getattr(auth_result, "user", None)
    if not session or not user:
        raise AppError("Failed to create session after sign-up", 500)

    set_auth_cookies(
        response,
        access_token=getattr(session, "access_token", ""),
        refresh_token=getattr(session, "refresh_token", ""),
        expires_in=getattr(session, "expires_in", None),
    )
    return {"user": map_user(user)}


def sign_in(payload: SignInInput, response: Response):
    try:
        auth_result = supabase_anon.auth.sign_in_with_password({"email": payload.email, "password": payload.password})
    except Exception as exc:
        raise AppError("Unauthorized", 401, str(exc)) from exc

    session = getattr(auth_result, "session", None)
    user = getattr(auth_result, "user", None)
    if not session or not user:
        raise AppError("Session missing while signing in", 500)

    set_auth_cookies(
        response,
        access_token=getattr(session, "access_token", ""),
        refresh_token=getattr(session, "refresh_token", ""),
        expires_in=getattr(session, "expires_in", None),
    )
    return {"user": map_user(user)}


def refresh(payload: RefreshInput, request: Request, response: Response):
    token = payload.refreshToken or request.cookies.get(settings.refresh_token_cookie_name)
    if not token:
        raise AppError("Refresh token missing", 401)

    try:
        try:
            auth_result = supabase_anon.auth.refresh_session(token)
        except TypeError:
            auth_result = supabase_anon.auth.refresh_session({"refresh_token": token})
    except Exception as exc:
        raise AppError("Unauthorized", 401, str(exc)) from exc

    session = getattr(auth_result, "session", None)
    user = getattr(auth_result, "user", None)
    if not session or not user:
        raise AppError("Session missing while refreshing tokens", 500)

    set_auth_cookies(
        response,
        access_token=getattr(session, "access_token", ""),
        refresh_token=getattr(session, "refresh_token", ""),
        expires_in=getattr(session, "expires_in", None),
    )
    return {"user": map_user(user)}


async def sign_out(request: Request, response: Response, authorization: str | None):
    token = extract_access_token(request, authorization)
    if token:
        await revoke_supabase_session(token)
    clear_auth_cookies(response)


def request_password_reset(payload: ForgotPasswordInput):
    # Always return a generic response to avoid account enumeration.
    generic_message = "If an account exists for that email, a reset link has been sent."

    if not settings.smtp_configured:
        raise AppError(
            "SMTP is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_FROM_EMAIL and credentials if required.",
            500,
        )

    user = _find_user_by_email(payload.email)
    if not user:
        return {"message": generic_message}

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    app_db().table("password_reset_tokens").insert(
        {
            "user_id": getattr(user, "id", None),
            "email": payload.email,
            "token_hash": token_hash,
            "expires_at": expires_at,
        }
    ).execute()

    reset_base = _get_reset_base_url()
    reset_url = f"{reset_base}/reset-password?email={quote(payload.email)}&token={quote(raw_token)}"
    send_password_reset_email(payload.email, reset_url)

    return {"message": generic_message}


def reset_password(payload: ResetPasswordInput):
    token_hash = _hash_token(payload.token)
    now_iso = datetime.now(timezone.utc).isoformat()

    token_res = (
        app_db()
        .table("password_reset_tokens")
        .select("id,email,expires_at,used_at")
        .eq("email", payload.email)
        .eq("token_hash", token_hash)
        .is_("used_at", "null")
        .gt("expires_at", now_iso)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    token_row = (token_res.data or [None])[0]
    if not token_row:
        raise AppError("Invalid or expired reset token", 400)

    user = _find_user_by_email(payload.email)
    if not user:
        raise AppError("Invalid or expired reset token", 400)

    try:
        supabase_admin.auth.admin.update_user_by_id(
            getattr(user, "id", ""),
            {
                "password": payload.password,
            },
        )
    except Exception as exc:
        raise AppError("Failed to reset password", 500, str(exc)) from exc

    app_db().table("password_reset_tokens").update(
        {"used_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", token_row.get("id")).execute()

    return {"message": "Password reset successful."}
