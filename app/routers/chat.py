import os
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.dependencies import get_current_user, get_supabase
from app.services.llm.nim_client import call_seviyan, _is_off_topic

logger = logging.getLogger("zenu.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])

CRISIS_PHRASES = [
    "hurt myself", "end it", "don't want to be here",
    "want to die", "kill myself", "give up on life",
    "no reason to live", "better off dead", "end my life"
]

CRISIS_RESPONSE = (
    "I hear you, and I'm really glad you reached out. "
    "What you're feeling matters deeply. Please contact iCall right now — "
    "free and confidential: 📞 9152987821. "
    "Or Vandrevala Foundation: 1860-2662-345 (available 24/7). "
    "You are not alone. 💙"
)


class ChatMessageIn(BaseModel):
    message: str
    conversation_history: list = []


@router.post("/message")
async def send_message(
    payload: ChatMessageIn,
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    msg_lower = payload.message.lower()

    # Layer 1: Crisis detection — hard block, no LLM call
    if any(phrase in msg_lower for phrase in CRISIS_PHRASES):
        return {
            "reply": CRISIS_RESPONSE,
            "safety_triggered": True,
            "trigger_type": "crisis"
        }

    # Layer 2: Off-topic detection — soft redirect, no LLM call
    if _is_off_topic(payload.message):
        import random
        from app.services.llm.nim_client import OFF_TOPIC_RESPONSES
        return {
            "reply": random.choice(OFF_TOPIC_RESPONSES),
            "safety_triggered": True,
            "trigger_type": "off_topic"
        }

    # Layer 3: NIM call with wellness system prompt
    messages = payload.conversation_history[-10:] + [
        {"role": "user", "content": payload.message}
    ]
    journal_context = _get_journal_context(sb, str(user.id))
    reply = call_seviyan(messages=messages, journal_context=journal_context)

    return {
        "reply": reply,
        "safety_triggered": False,
        "trigger_type": None
    }


def _get_journal_context(sb, user_id: str) -> str:
    try:
        res = sb.table("journal_entries").select("content, created_at") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True).limit(3).execute()
        if not res.data:
            return ""
        return " | ".join(
            r["content"][:150] for r in res.data if r.get("content")
        )
    except Exception:
        return ""

@router.get("/conversations")
async def get_conversations(
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    """
    Returns the user's past conversation sessions.
    For now returns an empty list since conversations are stored client-side.
    This endpoint exists to satisfy the frontend contract.
    """
    try:
        # Try to fetch from chat_sessions table if it exists
        res = sb.table("chat_sessions") \
            .select("id, title, created_at, updated_at") \
            .eq("user_id", str(user.id)) \
            .order("updated_at", desc=True) \
            .limit(20) \
            .execute()
        return {"conversations": res.data or []}
    except Exception:
        # Table may not exist yet — return empty list gracefully
        return {"conversations": []}

class ConversationIn(BaseModel):
    title: Optional[str] = "New conversation"

@router.post("/conversations")
async def create_conversation(
    payload: ConversationIn,
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    try:
        res = sb.table("chat_sessions").insert({
            "user_id": str(user.id),
            "title": payload.title,
        }).execute()
        return {"conversation": res.data[0] if res.data else {"id": None, "title": payload.title}}
    except Exception:
        return {"conversation": {"id": None, "title": payload.title}}
