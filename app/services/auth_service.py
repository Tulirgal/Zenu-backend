from __future__ import annotations

import base64
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
    set_auth_cookies,
)
from app.core.supabase import app_db, supabase_admin, supabase_anon
from app.schemas import (
    ForgotPasswordInput,
    GoogleSessionInput,
    RefreshInput,
    ResetPasswordInput,
    SignInInput,
    SignUpInput,
)
from app.services.oauth_store import create_oauth_ticket, pop_oauth_start, pop_oauth_ticket, save_oauth_start
from app.services.smtp_service import send_password_reset_email

logger = logging.getLogger("zenu.auth")

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


def _iter_auth_users():
    page = 1
    per_page = 200
    while True:
        users = supabase_admin.auth.admin.list_users(page=page, per_page=per_page)
        if not users:
            return
        for user in users:
            yield user
        if len(users) < per_page:
            return
        page += 1


def _find_user_by_email(email: str):
    target = email.lower()
    for user in _iter_auth_users():
        user_email = (getattr(user, "email", None) or "").lower()
        if user_email == target:
            return user
    return None


def _find_user_by_google_sub(google_sub: str):
    for user in _iter_auth_users():
        metadata = getattr(user, "user_metadata", None) or {}
        if metadata.get("google_sub") == google_sub:
            return user
    return None


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


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


def _merge_user_metadata(existing_metadata: dict | None, updates: dict) -> dict:
    merged = dict(existing_metadata or {})
    for key, value in updates.items():
        if value is not None and value != "":
            merged[key] = value
    return merged


def _upsert_google_user(*, email: str, full_name: str | None, picture: str | None, google_sub: str):
    """
    Map Google identity → ZenU user via stable google_sub.
    Email-only linking is only allowed when the existing account has no other google_sub.
    """
    metadata_updates = {
        "full_name": full_name,
        "avatar_url": picture,
        "provider": "google",
        "google_sub": google_sub,
    }

    by_sub = _find_user_by_google_sub(google_sub)
    if by_sub:
        try:
            supabase_admin.auth.admin.update_user_by_id(
                getattr(by_sub, "id", ""),
                {
                    "user_metadata": _merge_user_metadata(getattr(by_sub, "user_metadata", None), metadata_updates),
                    "email_confirm": True,
                },
            )
        except Exception as exc:
            logger.warning("Google user metadata update skipped: %s", exc)
        return by_sub

    by_email = _find_user_by_email(email)
    if by_email:
        existing_meta = getattr(by_email, "user_metadata", None) or {}
        existing_sub = existing_meta.get("google_sub")
        if existing_sub and existing_sub != google_sub:
            raise AppError("Account conflict", 409, "existing_account")
        try:
            supabase_admin.auth.admin.update_user_by_id(
                getattr(by_email, "id", ""),
                {
                    "user_metadata": _merge_user_metadata(existing_meta, metadata_updates),
                    "email_confirm": True,
                },
            )
        except Exception as exc:
            logger.warning("Google account link metadata update skipped: %s", exc)
        return by_email

    try:
        created = supabase_admin.auth.admin.create_user(
            {
                "email": email,
                "email_confirm": True,
                "password": secrets.token_urlsafe(32),
                "user_metadata": {k: v for k, v in metadata_updates.items() if v},
                "app_metadata": {"provider": "google", "providers": ["google"]},
            }
        )
    except Exception as exc:
        existing = _find_user_by_google_sub(google_sub) or _find_user_by_email(email)
        if existing:
            return existing
        raise AppError("Failed to create Google user", 400, str(exc)) from exc

    return getattr(created, "user", None) or created


def start_google_oauth(request: Request, _response: Response) -> RedirectResponse:
    """
    OAuth 2.0 Authorization Code start (Web application client).
    ZenU FastAPI owns the flow — not Supabase Auth OAuth.
    """
    frontend = _frontend_origin()
    if not settings.google_oauth_configured:
        return RedirectResponse(
            url=f"{frontend}/signin?oauth_error=google_not_configured",
            status_code=302,
        )

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _pkce_pair()
    save_oauth_start(state, code_verifier)

    redirect_uri = _google_redirect_uri(request)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
    }
    authorize_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    logger.info("Google OAuth authorize redirect_uri=%s", redirect_uri)
    return RedirectResponse(url=authorize_url, status_code=302)


def complete_google_oauth(
    request: Request,
    _response: Response,
    code: str | None,
    error: str | None,
    state: str | None = None,
):
    """
    OAuth 2.0 callback: validate state, exchange authorization code, create ZenU session ticket.
    Google redirects here directly (not via Vercel proxy).
    """
    frontend = _frontend_origin()
    if error:
        return RedirectResponse(url=f"{frontend}/signin?oauth_error={quote(error)}", status_code=302)
    if not code:
        return RedirectResponse(url=f"{frontend}/signin?oauth_error=missing_code", status_code=302)
    if not state:
        return RedirectResponse(url=f"{frontend}/signin?oauth_error=invalid_state", status_code=302)
    if not settings.google_oauth_configured:
        return RedirectResponse(url=f"{frontend}/signin?oauth_error=google_not_configured", status_code=302)

    start_record = pop_oauth_start(state)
    if not start_record:
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
                    "code_verifier": start_record.code_verifier,
                },
                headers={"Accept": "application/json"},
            )
            if token_res.status_code >= 400:
                logger.warning("Google token exchange failed status=%s", token_res.status_code)
                return RedirectResponse(url=f"{frontend}/signin?oauth_error=exchange_failed", status_code=302)

            tokens = token_res.json()
            google_access = tokens.get("access_token")
            if not google_access:
                return RedirectResponse(url=f"{frontend}/signin?oauth_error=identity_missing", status_code=302)

            info_res = client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {google_access}"},
            )
            if info_res.status_code >= 400:
                logger.warning("Google userinfo failed status=%s", info_res.status_code)
                return RedirectResponse(url=f"{frontend}/signin?oauth_error=identity_invalid", status_code=302)

            info = info_res.json()

        google_sub = (info.get("sub") or "").strip()
        email = (info.get("email") or "").strip().lower()
        if not google_sub:
            return RedirectResponse(url=f"{frontend}/signin?oauth_error=identity_invalid", status_code=302)
        if not email:
            return RedirectResponse(url=f"{frontend}/signin?oauth_error=email_missing", status_code=302)
        if info.get("email_verified") is False:
            return RedirectResponse(url=f"{frontend}/signin?oauth_error=email_unverified", status_code=302)

        _upsert_google_user(
            email=email,
            full_name=info.get("name"),
            picture=info.get("picture"),
            google_sub=google_sub,
        )

        session, user = _create_session_for_email(email)
        ensure_profile_for_user(user)

        ticket = create_oauth_ticket(
            access_token=getattr(session, "access_token", ""),
            refresh_token=getattr(session, "refresh_token", ""),
            expires_in=getattr(session, "expires_in", None),
            user_payload=map_user(user),
        )
        # Handoff via frontend so /api/proxy can attach HttpOnly cookies on the Vercel host.
        return RedirectResponse(
            url=f"{frontend}/auth/google/complete?ticket={quote(ticket)}",
            status_code=302,
        )
    except AppError as exc:
        code_name = str(exc.details or exc.message or "callback_failed").replace(" ", "_")
        logger.warning("Google OAuth app error: %s", exc.message)
        return RedirectResponse(url=f"{frontend}/signin?oauth_error={quote(code_name)}", status_code=302)
    except Exception:
        logger.exception("Google OAuth callback failed")
        return RedirectResponse(url=f"{frontend}/signin?oauth_error=callback_failed", status_code=302)


def exchange_google_session(payload: GoogleSessionInput, response: Response):
    """Consume one-time OAuth ticket and set the same ZenU auth cookies as email/password."""
    record = pop_oauth_ticket(payload.ticket.strip())
    if not record:
        raise AppError("Invalid or expired Google session ticket", 401)

    set_auth_cookies(
        response,
        access_token=record.access_token,
        refresh_token=record.refresh_token,
        expires_in=record.expires_in,
    )
    return {"user": record.user_payload}


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
        raise AppError(str(exc) or "Failed to create user", 400, str(exc)) from exc

    try:
        auth_result = supabase_anon.auth.sign_in_with_password({"email": payload.email, "password": payload.password})
    except Exception as exc:
        raise AppError(str(exc) or "Failed to create session after sign-up", 500, str(exc)) from exc

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
        raise AppError(str(exc) or "Unauthorized", 401, str(exc)) from exc

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
        raise AppError(str(exc) or "Unauthorized", 401, str(exc)) from exc

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


def delete_account(user_id: str) -> None:
    try:
        supabase_admin.auth.admin.delete_user(user_id)
    except Exception as e:
        logger.error(f"Failed to delete user account {user_id}: {e}")
        raise AppError(500, "Failed to permanently delete account.")
