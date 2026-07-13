from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.core.dependencies import AuthContext, require_auth
from app.schemas import GratitudeCreateInput
from app.services import gratitude_service

router = APIRouter(tags=["gratitude"])


@router.get("/api/gratitude/entries")
async def gratitude_entries(auth: AuthContext = Depends(require_auth)):
    return gratitude_service.list_entries(auth.user["id"])


@router.post("/api/gratitude/entries", status_code=201)
async def gratitude_create(payload: GratitudeCreateInput, auth: AuthContext = Depends(require_auth)):
    return gratitude_service.create_entry(auth.user["id"], payload)


@router.delete("/api/gratitude/entries/{entry_id}", status_code=204)
async def gratitude_delete(entry_id: str, auth: AuthContext = Depends(require_auth)):
    gratitude_service.delete_entry(auth.user["id"], entry_id)
    return Response(status_code=204)


@router.get("/api/gratitude/random-feedback")
async def gratitude_random_feedback(auth: AuthContext = Depends(require_auth)):
    return gratitude_service.random_feedback(auth.user["id"])


@router.get("/api/gratitude/overall-review")
async def gratitude_overall_review(auth: AuthContext = Depends(require_auth)):
    return gratitude_service.overall_review(auth.user["id"])
