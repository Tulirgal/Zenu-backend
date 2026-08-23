from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from app.core.dependencies import AuthContext, require_auth
from app.core.security import map_user, clear_auth_cookies
from app.schemas import (
    ForgotPasswordInput,
    GoogleSessionInput,
    RefreshInput,
    ResetPasswordInput,
    SignInInput,
    SignUpInput,
)
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post("/api/auth/sign-up", status_code=201)
async def sign_up(payload: SignUpInput, response: Response):
    return auth_service.sign_up(payload, response)


@router.post("/api/auth/sign-in")
async def sign_in(payload: SignInInput, response: Response):
    return auth_service.sign_in(payload, response)


@router.get("/api/auth/google")
async def google_oauth_start(request: Request, response: Response):
    """OAuth 2.0 Authorization Code start → 302 to Google."""
    return auth_service.start_google_oauth(request, response)


@router.get("/api/auth/callback")
async def google_oauth_callback(
    request: Request,
    response: Response,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
):
    """OAuth 2.0 callback: code exchange + ZenU session ticket (Google redirects here directly)."""
    err = error_description or error
    return auth_service.complete_google_oauth(request, response, code, err, state)


@router.post("/api/auth/google/session")
async def google_oauth_session(payload: GoogleSessionInput, response: Response):
    """Exchange one-time OAuth ticket for the same HttpOnly ZenU auth cookies as email/password."""
    return auth_service.exchange_google_session(payload, response)


@router.post("/api/auth/refresh")
async def refresh(payload: RefreshInput, request: Request, response: Response):
    return auth_service.refresh(payload, request, response)


@router.post("/api/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordInput):
    return auth_service.request_password_reset(payload)


@router.post("/api/auth/reset-password")
async def reset_password(payload: ResetPasswordInput):
    return auth_service.reset_password(payload)


@router.post("/api/auth/sign-out", status_code=204)
async def sign_out(request: Request, response: Response, authorization: str | None = Header(default=None)):
    await auth_service.sign_out(request, response, authorization)
    return Response(status_code=204)


@router.get("/api/auth/me")
async def auth_me(auth: AuthContext = Depends(require_auth)):
    return {"user": map_user(type("SimpleUser", (), auth.user)())}


@router.get("/api/me")
async def api_me(auth: AuthContext = Depends(require_auth)):
    return {"user": map_user(type("SimpleUser", (), auth.user)())}


@router.post("/api/logout", status_code=204)
async def api_logout(
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
    _: AuthContext = Depends(require_auth),
):
    await auth_service.sign_out(request, response, authorization)
    return Response(status_code=204)


@router.delete("/api/user", status_code=204)
async def delete_user_account(
    response: Response,
    auth: AuthContext = Depends(require_auth)
):
    user_id = auth.user["id"]
    auth_service.delete_account(user_id)
    clear_auth_cookies(response)
    return Response(status_code=204)
