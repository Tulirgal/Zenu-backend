from __future__ import annotations

import random

from app.core.errors import AppError
from app.core.supabase import app_db
from app.schemas import GratitudeCreateInput
from app.services.common import extract_json_object, get_gemini_model, heuristic_gratitude_score


def list_entries(user_id: str):
    result = (
        app_db()
        .table("journal_entries")
        .select("id,title,content,created_at,mood")
        .eq("user_id", user_id)
        .ilike("mood", "grateful")
        .order("created_at", desc=True)
        .execute()
    )
    rows = result.data or []
    return [
        {"id": row.get("id"), "title": row.get("title"), "content": row.get("content"), "createdAt": row.get("created_at")}
        for row in rows
    ]


def create_entry(user_id: str, payload: GratitudeCreateInput):
    result = (
        app_db()
        .table("journal_entries")
        .insert({"user_id": user_id, "mood": "Grateful", "title": payload.title, "content": payload.content})
        .execute()
    )
    row = (result.data or [{}])[0]
    return {"id": row.get("id"), "title": row.get("title"), "content": row.get("content"), "createdAt": row.get("created_at")}


def delete_entry(user_id: str, entry_id: str):
    existing = app_db().table("journal_entries").select("id,user_id,mood").eq("id", entry_id).limit(1).execute()
    row = (existing.data or [None])[0]
    if not row:
        raise AppError("Gratitude entry not found", 404)
    if row.get("user_id") != user_id:
        raise AppError("Cannot access this gratitude entry", 403)
    if str(row.get("mood", "")).lower() != "grateful":
        raise AppError("Entry is not a gratitude journal item", 400)

    app_db().table("journal_entries").delete().eq("id", entry_id).execute()


def random_feedback(user_id: str):
    result = (
        app_db()
        .table("journal_entries")
        .select("id,title,content,created_at,mood")
        .eq("user_id", user_id)
        .ilike("mood", "grateful")
        .order("created_at", desc=True)
        .execute()
    )
    entries = result.data or []
    if not entries:
        raise AppError("No gratitude entries found yet", 404)

    entry = random.choice(entries)
    content = str(entry.get("content") or "")
    fallback_score = heuristic_gratitude_score(content)
    fallback_feedback = (
        "This reflection shows strong appreciation and emotional clarity. Keep naming specific people and moments."
        if fallback_score >= 8
        else "This is a thoughtful gratitude entry. Adding one concrete detail about why it mattered can deepen the effect."
    )

    score = fallback_score
    feedback = fallback_feedback

    model = get_gemini_model()
    if model:
        prompt = "\n".join(
            [
                "You are a warm gratitude coach.",
                "Analyze the gratitude entry and return strict JSON only in this shape:",
                '{"thankfulnessScore": number between 1 and 10, "feedback": "2-4 sentence supportive feedback"}',
                "Do not add markdown fences.",
                "",
                f"Entry title: {entry.get('title') or 'Untitled'}",
                f"Entry content: {content}",
            ]
        )
        try:
            generated = model.generate_content(prompt)
            generated_text = getattr(generated, "text", "") or ""
            parsed = extract_json_object(generated_text)
            if parsed:
                maybe_score = parsed.get("thankfulnessScore")
                maybe_feedback = parsed.get("feedback")
                if isinstance(maybe_score, (int, float)):
                    score = max(1, min(10, int(round(maybe_score))))
                if isinstance(maybe_feedback, str) and maybe_feedback.strip():
                    feedback = maybe_feedback.strip()
        except Exception:
            pass

    return {
        "entry": {"id": entry.get("id"), "title": entry.get("title"), "content": entry.get("content"), "createdAt": entry.get("created_at")},
        "thankfulnessScore": score,
        "feedback": feedback,
    }


def overall_review(user_id: str):
    result = (
        app_db()
        .table("journal_entries")
        .select("id,title,content,created_at,mood")
        .eq("user_id", user_id)
        .ilike("mood", "grateful")
        .order("created_at", desc=True)
        .execute()
    )
    entries = result.data or []
    if not entries:
        raise AppError("No gratitude entries found yet", 404)

    limited = entries[:30]
    combined = "\n".join([f"{idx + 1}. {entry.get('title') or 'Untitled'} :: {entry.get('content') or ''}" for idx, entry in enumerate(limited)])

    review_text: str | None = None
    model = get_gemini_model()
    if model:
        prompt = "\n".join(
            [
                "You are a warm gratitude coach.",
                "Give a concise overall review of these gratitude journal entries.",
                "Output plain text with these sections:",
                "1) Overall thankfulness trend (2-3 sentences)",
                "2) Strengths observed (3 bullets)",
                "3) One next-step prompt for tomorrow (1 sentence)",
                "",
                combined,
            ]
        )
        try:
            generated = model.generate_content(prompt)
            review_text = (getattr(generated, "text", "") or "").strip() or None
        except Exception:
            review_text = None

    if not review_text:
        avg_score = sum(heuristic_gratitude_score(str(entry.get("content") or "")) for entry in entries) / len(entries)
        review_text = "\n".join(
            [
                f"Overall thankfulness trend: Your average gratitude intensity is around {avg_score:.1f}/10 across {len(entries)} entries.",
                "Strengths observed:",
                "- You are consistently capturing meaningful positive moments.",
                "- Your entries show personal reflection, not just event logging.",
                "- You are building a repeatable gratitude habit.",
                "One next-step prompt for tomorrow: Name one hard moment and one thing inside it that still deserves gratitude.",
            ]
        )

    return {"entriesCount": len(entries), "review": review_text}
