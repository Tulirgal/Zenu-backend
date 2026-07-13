from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import AuthContext, require_auth
from app.schemas import BreathingSessionInput
from app.services import breathing_service

router = APIRouter(tags=["breathing"])


@router.get("/api/breathing/patterns")
async def breathing_patterns(_: AuthContext = Depends(require_auth)):
    return breathing_service.get_patterns()


@router.post("/api/breathing/sessions", status_code=201)
async def breathing_sessions(payload: BreathingSessionInput, auth: AuthContext = Depends(require_auth)):
    return breathing_service.create_session(auth.user["id"], payload)
