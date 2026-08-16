from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.dependencies import get_current_user, get_app_db
from app.services.agentic.module_ids import resolve_canonical_module_id

router = APIRouter(prefix="/api/signals", tags=["signals"])

ALLOWED_EVENT_TYPES = frozenset({
    "opened",
    "started",
    "completed",
    "skipped",
    "abandoned",
})

_MOOD_LABELS = {
    1: "Low",
    2: "Okay",
    3: "Calm",
    4: "Good",
    5: "Great",
    6: "Great",
    7: "Great",
    8: "Great",
    9: "Great",
    10: "Great",
}


class MoodLogIn(BaseModel):
    mood_score: int = Field(..., ge=1, le=10)
    note: Optional[str] = None
    source: Optional[str] = None


class PSSScoreIn(BaseModel):
    raw_score: int = Field(..., ge=0, le=40)


class EngagementEventIn(BaseModel):
    module_id: str
    event_type: str
    duration_sec: Optional[int] = None
    recommendation_log_id: Optional[str] = None


@router.post("/mood")
async def log_mood(payload: MoodLogIn, user=Depends(get_current_user), sb=Depends(get_app_db)):
    """Write mood into app.mood_logs (canonical)."""
    row = {
        "user_id":    str(user.id),
        "mood_score": payload.mood_score,
        "intensity":  payload.mood_score,
        "mood":       _MOOD_LABELS.get(payload.mood_score, "Calm"),
        "note":       payload.note,
        "source":     payload.source or "signal",
    }
    sb.table("mood_logs").insert(row).execute()
    return {"status": "ok"}


@router.post("/pss")
async def log_pss(payload: PSSScoreIn, user=Depends(get_current_user), sb=Depends(get_app_db)):
    """Write compact PSS into app.pss_scores (canonical)."""
    sb.table("pss_scores").insert({
        "user_id":   str(user.id),
        "raw_score": payload.raw_score,
    }).execute()
    return {"status": "ok"}


@router.post("/engagement")
async def log_engagement(
    payload: EngagementEventIn,
    user=Depends(get_current_user),
    sb=Depends(get_app_db),
):
    """Write engagement into app.engagement_events with canonical module_id."""
    event_type = (payload.event_type or "").strip().lower()
    if event_type not in ALLOWED_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"event_type must be one of: {', '.join(sorted(ALLOWED_EVENT_TYPES))}",
        )

    canonical = resolve_canonical_module_id(sb, payload.module_id)
    row = {
        "user_id":      str(user.id),
        "module_id":    canonical,
        "event_type":   event_type,
        "duration_sec": payload.duration_sec,
    }
    if payload.recommendation_log_id:
        row["recommendation_log_id"] = payload.recommendation_log_id

    sb.table("engagement_events").insert(row).execute()
    return {"status": "ok"}
