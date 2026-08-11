from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional
from app.dependencies import get_current_user, get_supabase

router = APIRouter(prefix="/api/signals", tags=["signals"])


class MoodLogIn(BaseModel):
    mood_score: int = Field(..., ge=1, le=10)
    note: Optional[str] = None


class PSSScoreIn(BaseModel):
    raw_score: int = Field(..., ge=0, le=40)


class EngagementEventIn(BaseModel):
    module_id: str
    event_type: str
    duration_sec: Optional[int] = None


@router.post("/mood")
async def log_mood(payload: MoodLogIn, user=Depends(get_current_user), sb=Depends(get_supabase)):
    sb.table("mood_logs").insert({
        "user_id":    str(user.id),
        "mood_score": payload.mood_score,
        "note":       payload.note,
    }).execute()
    return {"status": "ok"}


@router.post("/pss")
async def log_pss(payload: PSSScoreIn, user=Depends(get_current_user), sb=Depends(get_supabase)):
    sb.table("pss_scores").insert({
        "user_id":   str(user.id),
        "raw_score": payload.raw_score,
    }).execute()
    return {"status": "ok"}


@router.post("/engagement")
async def log_engagement(payload: EngagementEventIn, user=Depends(get_current_user), sb=Depends(get_supabase)):
    sb.table("engagement_events").insert({
        "user_id":      str(user.id),
        "module_id":    payload.module_id,
        "event_type":   payload.event_type,
        "duration_sec": payload.duration_sec,
    }).execute()
    return {"status": "ok"}
