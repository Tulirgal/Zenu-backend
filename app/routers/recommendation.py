from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from app.dependencies import get_current_user, get_app_db
from app.services.agentic.controller import AgenticController

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/today")
async def get_today_recommendations(
    top_n: int = 3,
    user=Depends(get_current_user),
    sb=Depends(get_app_db),
):
    """Recommendations from the existing agentic engine; data plane = app schema."""
    controller = AgenticController(supabase=sb, user_id=str(user.id))
    return controller.get_recommendations(top_n=top_n)


class FeedbackIn(BaseModel):
    modules_accepted: List[str]


@router.post("/{log_id}/feedback")
async def submit_feedback(
    log_id: str,
    payload: FeedbackIn,
    user=Depends(get_current_user),
    sb=Depends(get_app_db),
):
    accepted = [{"module_id": mid} for mid in payload.modules_accepted]
    sb.table("recommendation_log").update({
        "modules_accepted": accepted
    }).eq("id", log_id).eq("user_id", str(user.id)).execute()
    return {"status": "ok"}
