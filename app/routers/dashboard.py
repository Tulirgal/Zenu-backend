from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.core.dependencies import AuthContext, require_auth
from app.schemas import ActivityInput, PSSInput
from app.services import dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard/home")
async def dashboard_home(_: AuthContext = Depends(require_auth)):
    return dashboard_service.get_home_overview()


@router.get("/api/dashboard/streak")
async def dashboard_streak(auth: AuthContext = Depends(require_auth)):
    return dashboard_service.get_streak_summary(auth.user["id"])


@router.post("/api/dashboard/activity", status_code=204)
async def dashboard_activity(payload: ActivityInput, auth: AuthContext = Depends(require_auth)):
    dashboard_service.record_activity(auth.user["id"], payload)
    return Response(status_code=204)


@router.get("/api/dashboard/pss")
async def dashboard_pss(auth: AuthContext = Depends(require_auth)):
    return dashboard_service.get_latest_pss(auth.user["id"])


@router.post("/api/dashboard/pss", status_code=201)
async def dashboard_pss_create(payload: PSSInput, auth: AuthContext = Depends(require_auth)):
    return dashboard_service.create_pss(auth.user["id"], payload)
