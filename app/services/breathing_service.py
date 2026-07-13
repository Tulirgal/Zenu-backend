from __future__ import annotations

from app.core.errors import AppError
from app.core.supabase import app_db
from app.schemas import BreathingSessionInput


def get_patterns():
    result = app_db().table("breathing_patterns").select("*").order("created_at").execute()
    rows = result.data or []
    return [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "description": row.get("description"),
            "difficulty": row.get("difficulty"),
            "steps": row.get("steps") or [],
            "defaultMinutes": int(row.get("default_minutes") or 0),
        }
        for row in rows
    ]


def create_session(user_id: str, payload: BreathingSessionInput):
    verify = app_db().table("breathing_patterns").select("id").eq("id", payload.patternId).limit(1).execute()
    if not (verify.data or []):
        raise AppError("Breathing pattern not found", 404)

    app_db().table("breathing_sessions").insert(
        {
            "user_id": user_id,
            "pattern": payload.patternId,
            "duration_seconds": payload.durationSeconds,
            "rating": payload.rating,
            "notes": payload.notes,
        }
    ).execute()

    return {"success": True}
