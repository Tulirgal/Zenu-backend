from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import AuthContext, require_auth
from app.schemas import MeditationSessionInput
from app.services import meditation_service

router = APIRouter(tags=["meditation"])


@router.get("/api/meditations")
async def meditations(_: AuthContext = Depends(require_auth)):
    return meditation_service.get_meditations()


@router.post("/api/meditations/sessions", status_code=201)
async def meditation_sessions(payload: MeditationSessionInput, auth: AuthContext = Depends(require_auth)):
    return meditation_service.create_session(auth.user["id"], payload)
