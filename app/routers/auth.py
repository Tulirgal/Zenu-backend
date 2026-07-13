from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response

from app.core.dependencies import AuthContext, require_auth
from app.core.security import map_user
from app.schemas import ForgotPasswordInput, RefreshInput, ResetPasswordInput, SignInInput, SignUpInput
from app.services import auth_service

router = APIRouter(tags=["auth"])


@router.post("/api/auth/sign-up", status_code=201)
async def sign_up(payload: SignUpInput, response: Response):
    return auth_service.sign_up(payload, response)


@router.post("/api/auth/sign-in")
async def sign_in(payload: SignInInput, response: Response):
    return auth_service.sign_in(payload, response)


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
