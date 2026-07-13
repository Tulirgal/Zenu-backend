from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.errors import AppError
from app.core.supabase import app_db
from app.schemas import ActivityInput, PSSInput
from app.services.common import MODULE_SLUGS, compute_plant_stage, format_day_key, parse_iso_date


def get_home_overview():
    modules_res = app_db().table("modules").select("*").order("position").execute()
    now_iso = datetime.now(timezone.utc).isoformat()

    daily_res = (
        app_db()
        .table("daily_focus")
        .select("*")
        .lte("starts_at", now_iso)
        .order("starts_at", desc=True)
        .limit(5)
        .execute()
    )

    modules = modules_res.data or []
    all_focus = daily_res.data or []

    active_focus = None
    for row in all_focus:
        ends_at = row.get("ends_at")
        if not ends_at or parse_iso_date(ends_at) > datetime.now(timezone.utc):
            active_focus = {
                "title": row.get("title"),
                "durationSeconds": int(row.get("duration_seconds") or 0),
                "cta": row.get("cta"),
                "description": row.get("description"),
                "moduleId": row.get("module_id"),
            }
            break

    mapped_modules = [
        {
            "id": row.get("id"),
            "title": row.get("title"),
            "description": row.get("description"),
            "icon": row.get("icon"),
            "position": row.get("position"),
        }
        for row in modules
    ]

    return {"modules": mapped_modules, "dailyFocus": active_focus}


def get_streak_summary(user_id: str):
    window_start = datetime.now(timezone.utc) - timedelta(days=30)
    logs_res = (
        app_db()
        .table("activity_logs")
        .select("occurred_at")
        .eq("user_id", user_id)
        .gte("occurred_at", window_start.isoformat())
        .order("occurred_at", desc=True)
        .execute()
    )

    rows = logs_res.data or []
    if not rows:
        return {"currentStreak": 0, "plantStage": "seedling", "lastActivity": None}

    unique_days: set[str] = set()
    last_activity: str | None = None

    for row in rows:
        occurred_at = row.get("occurred_at")
        if not occurred_at:
            continue
        dt = parse_iso_date(occurred_at)
        unique_days.add(format_day_key(dt))
        if last_activity is None or dt > parse_iso_date(last_activity):
            last_activity = dt.isoformat()

    cursor = datetime.now(timezone.utc)
    today_key = format_day_key(cursor)
    if today_key not in unique_days:
        cursor = cursor - timedelta(days=1)

    streak = 0
    while format_day_key(cursor) in unique_days:
        streak += 1
        cursor = cursor - timedelta(days=1)

    return {
        "currentStreak": streak,
        "plantStage": compute_plant_stage(streak),
        "lastActivity": last_activity,
    }


def record_activity(user_id: str, payload: ActivityInput):
    if payload.module not in MODULE_SLUGS:
        raise AppError("Invalid module", 400)

    app_db().table("activity_logs").insert(
        {
            "user_id": user_id,
            "module": payload.module,
            "payload": payload.payload or {},
        }
    ).execute()


def get_latest_pss(user_id: str):
    result = (
        app_db()
        .table("pss_assessments")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    row = (result.data or [None])[0]
    if not row:
        return {"scores": [], "last3WeeksHigh": False, "averageScore": 0, "createdAt": None}

    return {
        "scores": row.get("scores") or [],
        "last3WeeksHigh": bool(row.get("flagged")),
        "averageScore": float(row.get("average_score") or 0),
        "createdAt": row.get("created_at"),
    }


def create_pss(user_id: str, payload: PSSInput):
    scores = [int(x) for x in payload.scores]
    if len(scores) != 10:
        raise AppError("PSS-10 requires exactly 10 scores", 400)
    if any(x < 0 or x > 4 for x in scores):
        raise AppError("Each PSS score must be between 0 and 4", 400)

    average = round(sum(scores) / len(scores), 2)
    flagged = average >= 2.7

    created = (
        app_db()
        .table("pss_assessments")
        .insert(
            {
                "user_id": user_id,
                "scores": scores,
                "average_score": average,
                "flagged": flagged,
            }
        )
        .execute()
    )

    row = (created.data or [{}])[0]

    return {
        "scores": row.get("scores", scores),
        "last3WeeksHigh": bool(row.get("flagged", flagged)),
        "averageScore": float(row.get("average_score", average)),
        "createdAt": row.get("created_at"),
    }
