from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import httpx
from fastapi import Request, Response
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import (
    clear_auth_cookies,
    extract_access_token,
    map_user,
    revoke_supabase_session,
    set_auth_cookie,
    set_auth_cookies,
)
from app.core.supabase import app_db, supabase_admin, supabase_anon
from app.schemas import ForgotPasswordInput, RefreshInput, ResetPasswordInput, SignInInput, SignUpInput
from app.services.smtp_service import send_password_reset_email

logger = logging.getLogger("zenu.auth")

GOOGLE_OAUTH_STATE_COOKIE = "zenu-google-oauth-state"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


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


def _frontend_origin() -> str:
    if settings.frontend_origins:
        return settings.frontend_origins[0]
    if settings.frontend_url:
        return settings.frontend_url.split(",")[0].strip().rstrip("/")
    return "http://localhost:3000"


def _public_api_base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _google_redirect_uri(request: Request) -> str:
    if settings.google_redirect_uri:
        return settings.google_redirect_uri.rstrip("/")
    return f"{_public_api_base(request)}/api/auth/callback"


def ensure_profile_for_user(user) -> None:
    """
    Compatible with planned profile upsert architecture.
    Creates a missing app.profiles row for the auth user (no bulk backfill).
    Failures are non-fatal so auth still succeeds if grants/RLS block writes.
    """
    try:
        user_id = getattr(user, "id", None)
        if not user_id:
            return

        existing = (
            app_db()
            .table("profiles")
            .select("id")
            .eq("id", str(user_id))
            .limit(1)
            .execute()
        )
        if existing.data:
            return

        metadata = getattr(user, "user_metadata", None) or {}
        full_name = metadata.get("full_name") or metadata.get("name")
        username = metadata.get("username") or metadata.get("preferred_username") or full_name
        avatar_url = metadata.get("avatar_url") or metadata.get("picture")

        row: dict = {"id": str(user_id)}
        if full_name:
            row["full_name"] = str(full_name)[:120]
        if username:
            row["username"] = str(username).replace(" ", "_")[:32]
        if avatar_url:
            row["avatar_url"] = str(avatar_url)[:500]

        app_db().table("profiles").insert(row).execute()
    except Exception as exc:
        logger.warning("ensure_profile_for_user skipped: %s", exc)


def _create_session_for_email(email: str):
    """
    Establish a normal Supabase Auth session for an existing confirmed user
    without going through Supabase's Google provider.
    Uses admin magic-link generation + OTP verify (server-side only).
    """
    try:
        link = supabase_admin.auth.admin.generate_link({"type": "magiclink", "email": email})
    except Exception as exc:
        raise AppError("Failed to create Google session", 500, str(exc)) from exc

    props = getattr(link, "properties", None)
    if isinstance(link, dict):
        props = link.get("properties") or link
    hashed_token = None
    email_otp = None
    if props is not None:
        hashed_token = getattr(props, "hashed_token", None) or (props.get("hashed_token") if isinstance(props, dict) else None)
        email_otp = getattr(props, "email_otp", None) or (props.get("email_otp") if isinstance(props, dict) else None)

    try:
        if hashed_token:
            auth_result = supabase_anon.auth.verify_otp({"type": "magiclink", "token_hash": hashed_token})
        elif email_otp:
            auth_result = supabase_anon.auth.verify_otp({"type": "email", "email": email, "token": email_otp})
        else:
            raise AppError("Failed to create Google session", 500, "Missing magic link token")
    except AppError:
        raise
    except Exception as exc:
        raise AppError("Failed to create Google session", 500, str(exc)) from exc

    session = getattr(auth_result, "session", None)
    user = getattr(auth_result, "user", None)
    if not session or not user:
        raise AppError("Failed to create Google session", 500, "Session missing")
    return session, user


def _upsert_google_user(email: str, full_name: str | None, picture: str | None, google_sub: str | None):
    existing = _find_user_by_email(email)
    metadata = {
        "full_name": full_name,
        "avatar_url": picture,
        "provider": "google",
        "google_sub": google_sub,
    }
    metadata = {k: v for k, v in metadata.items() if v}

    if existing:
        try:
            supabase_admin.auth.admin.update_user_by_id(
                getattr(existing, "id", ""),
                {"user_metadata": metadata, "email_confirm": True},
            )
        except Exception as exc:
            logger.warning("Google user metadata update skipped: %s", exc)
        return existing

    try:
        created = supabase_admin.auth.admin.create_user(
            {
                "email": email,
                "email_confirm": True,
                "password": secrets.token_urlsafe(32),
                "user_metadata": metadata,
                "app_metadata": {"provider": "google", "providers": ["google"]},
            }
        )
    except Exception as exc:
        # Race: email created between find and create
        existing = _find_user_by_email(email)
        if existing:
            return existing
        raise AppError("Failed to create Google user", 400, str(exc)) from exc

    user = getattr(created, "user", None) or created
    return user


def start_google_oauth(request: Request, _response: Response) -> RedirectResponse:
    """
    Begin Google OAuth using ZenU's own Google Cloud OAuth client (not Supabase Auth provider).
    """
    frontend = _frontend_origin()
    if not settings.google_oauth_configured:
        return RedirectResponse(
            url=f"{frontend}/signin?oauth_error=google_not_configured",
            status_code=302,
        )

    state = secrets.token_urlsafe(32)
    redirect_uri = _google_redirect_uri(request)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": state,
    }
    authorize_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    redirect = RedirectResponse(url=authorize_url, status_code=302)
    set_auth_cookie(redirect, GOOGLE_OAUTH_STATE_COOKIE, state, max_age=600)
    return redirect


def complete_google_oauth(
    request: Request,
    response: Response,
    code: str | None,
    error: str | None,
    state: str | None = None,
):
    """
    Google redirects here with ?code=&state=.
    Exchanges code with Google, upserts Auth user, sets existing ZenU cookies.
    """
    frontend = _frontend_origin()
    if error:
        return RedirectResponse(url=f"{frontend}/signin?oauth_error={quote(error)}", status_code=302)
    if not code:
        return RedirectResponse(url=f"{frontend}/signin?oauth_error=missing_code", status_code=302)
    if not settings.google_oauth_configured:
        return RedirectResponse(url=f"{frontend}/signin?oauth_error=google_not_configured", status_code=302)

    expected_state = request.cookies.get(GOOGLE_OAUTH_STATE_COOKIE)
    if not expected_state or not state or state != expected_state:
        return RedirectResponse(url=f"{frontend}/signin?oauth_error=invalid_state", status_code=302)

    redirect_uri = _google_redirect_uri(request)

    try:
        with httpx.Client(timeout=30) as client:
            token_res = client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            if token_res.status_code >= 400:
                logger.warning("Google token exchange failed: %s", token_res.text)
                return RedirectResponse(url=f"{frontend}/signin?oauth_error=exchange_failed", status_code=302)

            tokens = token_res.json()
            access_token = tokens.get("access_token")
            if not access_token:
                return RedirectResponse(url=f"{frontend}/signin?oauth_error=session_missing", status_code=302)

            info_res = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if info_res.status_code >= 400:
                logger.warning("Google userinfo failed: %s", info_res.text)
                return RedirectResponse(url=f"{frontend}/signin?oauth_error=userinfo_failed", status_code=302)

            info = info_res.json()

        email = (info.get("email") or "").strip().lower()
        if not email:
            return RedirectResponse(url=f"{frontend}/signin?oauth_error=email_missing", status_code=302)
        if info.get("email_verified") is False:
            return RedirectResponse(url=f"{frontend}/signin?oauth_error=email_unverified", status_code=302)

        _upsert_google_user(
            email=email,
            full_name=info.get("name"),
            picture=info.get("picture"),
            google_sub=info.get("sub"),
        )

        session, user = _create_session_for_email(email)
        ensure_profile_for_user(user)

        redirect = RedirectResponse(url=f"{frontend}/?auth=google", status_code=302)
        set_auth_cookies(
            redirect,
            access_token=getattr(session, "access_token", ""),
            refresh_token=getattr(session, "refresh_token", ""),
            expires_in=getattr(session, "expires_in", None),
        )
        set_auth_cookie(redirect, GOOGLE_OAUTH_STATE_COOKIE, "", max_age=0)
        return redirect
    except AppError as exc:
        logger.warning("Google OAuth app error: %s", exc.message)
        return RedirectResponse(url=f"{frontend}/signin?oauth_error={quote(exc.message)}", status_code=302)
    except Exception as exc:
        logger.exception("Google OAuth callback failed: %s", exc)
        return RedirectResponse(url=f"{frontend}/signin?oauth_error=callback_failed", status_code=302)


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
    ensure_profile_for_user(user)
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
    ensure_profile_for_user(user)
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
