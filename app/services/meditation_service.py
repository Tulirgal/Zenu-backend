from __future__ import annotations

from app.core.errors import AppError
from app.core.supabase import app_db
from app.schemas import MeditationSessionInput


def get_meditations():
    result = app_db().table("meditations").select("*").order("duration_minutes").execute()
    rows = result.data or []
    return [
        {
            "id": row.get("id"),
            "title": row.get("title"),
            "durationMinutes": int(row.get("duration_minutes") or 0),
            "category": row.get("category"),
            "imageUrl": row.get("image_url"),
            "audioUrl": row.get("audio_url"),
            "description": row.get("description"),
        }
        for row in rows
    ]


def create_session(user_id: str, payload: MeditationSessionInput):
    verify = app_db().table("meditations").select("id").eq("id", payload.meditationId).limit(1).execute()
    if not (verify.data or []):
        raise AppError("Meditation not found", 404)

    app_db().table("meditation_sessions").insert(
        {
            "user_id": user_id,
            "meditation_id": payload.meditationId,
            "duration_seconds": payload.durationSeconds,
        }
    ).execute()

    return {"success": True}
