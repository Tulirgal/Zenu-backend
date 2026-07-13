from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.errors import AppError
from app.core.supabase import app_db
from app.schemas import ChatInput
from app.services.common import get_gemini_model


def list_conversations(user_id: str):
    result = app_db().table("chat_conversations").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    rows = result.data or []
    return [{"id": row.get("id"), "title": row.get("title"), "createdAt": row.get("created_at")} for row in rows]


def get_messages(user_id: str, conversation_id: str):
    conversation = app_db().table("chat_conversations").select("id,user_id").eq("id", conversation_id).limit(1).execute()
    c_row = (conversation.data or [None])[0]
    if not c_row:
        raise AppError("Conversation not found", 404)
    if c_row.get("user_id") != user_id:
        raise AppError("Cannot access this conversation", 403)

    result = app_db().table("chat_messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
    rows = result.data or []
    return [{"id": int(row.get("id") or 0), "role": row.get("role"), "content": row.get("content"), "createdAt": row.get("created_at")} for row in rows]


def send_message(user_id: str, payload: ChatInput):
    message = payload.message.strip()
    if not message:
        raise AppError("Message cannot be empty", 400)

    conversation_id = payload.conversationId

    if conversation_id:
        c_result = app_db().table("chat_conversations").select("id,user_id,title,created_at").eq("id", conversation_id).limit(1).execute()
        c_row = (c_result.data or [None])[0]
        if not c_row:
            raise AppError("Conversation not found", 404)
        if c_row.get("user_id") != user_id:
            raise AppError("Cannot access this conversation", 403)
    else:
        conversation_create = app_db().table("chat_conversations").insert({"user_id": user_id, "title": message[:57] + "..." if len(message) > 60 else message}).execute()
        c_row = (conversation_create.data or [None])[0]
        if not c_row:
            raise AppError("Failed to create conversation", 500)
        conversation_id = c_row.get("id")

    app_db().table("chat_messages").insert({"conversation_id": conversation_id, "role": "user", "content": message}).execute()

    msg_result = app_db().table("chat_messages").select("*").eq("conversation_id", conversation_id).order("created_at").execute()
    messages = msg_result.data or []
    limited = messages[-20:]

    if not settings.gemini_api_key:
        raise AppError("Gemini API key is not configured", 500)

    model = get_gemini_model()
    if not model:
        raise AppError("Gemini API key is not configured", 500)

    history: list[dict[str, Any]] = []
    for item in limited[:-1]:
        role = "model" if item.get("role") == "assistant" else "user"
        text = str(item.get("content") or "").strip()
        if not text:
            continue
        if history and history[-1]["role"] == role:
            history[-1]["parts"][0]["text"] = f"{history[-1]['parts'][0]['text']}\n{text}".strip()
        else:
            history.append({"role": role, "parts": [{"text": text}]})

    try:
        chat = model.start_chat(history=history)
        generated = chat.send_message(str((limited[-1] if limited else {}).get("content") or message))
        reply = (getattr(generated, "text", "") or "").strip()
    except Exception as exc:
        raise AppError("Failed to generate assistant response", 502, str(exc)) from exc

    if not reply:
        raise AppError("The assistant did not return a response", 502)

    app_db().table("chat_messages").insert({"conversation_id": conversation_id, "role": "assistant", "content": reply}).execute()

    return {"conversationId": conversation_id, "reply": reply}
