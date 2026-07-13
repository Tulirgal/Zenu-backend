from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.errors import AppError
from app.core.supabase import app_db
from app.schemas import JournalCreateInput, JournalUpdateInput


def list_entries(user_id: str, limit: int, offset: int):
    if limit < 1 or limit > 100:
        raise AppError("limit must be between 1 and 100", 400)
    if offset < 0:
        raise AppError("offset must be >= 0", 400)

    result = (
        app_db()
        .table("journal_entries")
        .select("*")
        .eq("user_id", user_id)
        .neq("mood", "Grateful")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    rows = result.data or []
    return [
        {
            "id": row.get("id"),
            "mood": row.get("mood"),
            "title": row.get("title"),
            "content": row.get("content"),
            "createdAt": row.get("created_at"),
            "updatedAt": row.get("updated_at"),
        }
        for row in rows
    ]


def create_entry(user_id: str, payload: JournalCreateInput):
    result = (
        app_db()
        .table("journal_entries")
        .insert({"user_id": user_id, "mood": payload.mood, "title": payload.title, "content": payload.content})
        .execute()
    )
    row = (result.data or [{}])[0]
    return {
        "id": row.get("id"),
        "mood": row.get("mood"),
        "title": row.get("title"),
        "content": row.get("content"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def update_entry(user_id: str, entry_id: str, payload: JournalUpdateInput):
    existing = app_db().table("journal_entries").select("id,user_id").eq("id", entry_id).limit(1).execute()
    row = (existing.data or [None])[0]
    if not row:
        raise AppError("Journal entry not found", 404)
    if row.get("user_id") != user_id:
        raise AppError("Cannot modify this journal entry", 403)

    patch: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if payload.mood is not None:
        patch["mood"] = payload.mood
    if payload.title is not None:
        patch["title"] = payload.title
    if payload.content is not None:
        patch["content"] = payload.content

    updated = app_db().table("journal_entries").update(patch).eq("id", entry_id).execute()
    out = (updated.data or [{}])[0]
    return {
        "id": out.get("id"),
        "mood": out.get("mood"),
        "title": out.get("title"),
        "content": out.get("content"),
        "createdAt": out.get("created_at"),
        "updatedAt": out.get("updated_at"),
    }


def delete_entry(user_id: str, entry_id: str):
    existing = app_db().table("journal_entries").select("id,user_id").eq("id", entry_id).limit(1).execute()
    row = (existing.data or [None])[0]
    if not row:
        raise AppError("Journal entry not found", 404)
    if row.get("user_id") != user_id:
        raise AppError("Cannot modify this journal entry", 403)

    app_db().table("journal_entries").delete().eq("id", entry_id).execute()
