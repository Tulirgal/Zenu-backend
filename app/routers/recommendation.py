from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import AuthContext, require_auth
from app.services import recommendation_service

router = APIRouter(tags=["recommendation"])


@router.get("/api/recommendations/today")
async def recommendations_today(auth: AuthContext = Depends(require_auth)):
    return recommendation_service.get_recommendations(auth.user["id"])
