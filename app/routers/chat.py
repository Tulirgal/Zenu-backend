import logging
import re
import random
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.dependencies import get_current_user, get_supabase
from app.core.supabase import app_db
from app.services.llm.nim_client import call_seviyan, _is_off_topic, OFF_TOPIC_RESPONSES

logger = logging.getLogger("zenu.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])

CRISIS_PHRASES = [
    "hurt myself", "end it", "don't want to be here",
    "want to die", "kill myself", "give up on life",
    "no reason to live", "better off dead", "end my life",
]

CRISIS_RESPONSE = (
    "I hear you, and I'm really glad you reached out. "
    "What you're feeling matters deeply. Please contact iCall right now — "
    "free and confidential: 📞 9152987821. "
    "Or Vandrevala Foundation: 1860-2662-345 (24/7). "
    "You are not alone. 💙"
)


class ChatMessageIn(BaseModel):
    message: str
    session_id: Optional[str] = None


class ConversationIn(BaseModel):
    title: Optional[str] = "New conversation"


# ── POST send a message ─────────────────────────────────────────
@router.post("/message")
async def send_message(
    payload: ChatMessageIn,
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    uid = str(user.id)
    msg_lower = payload.message.lower()

    # Layer 1 — Crisis detection
    if any(phrase in msg_lower for phrase in CRISIS_PHRASES):
        reply = CRISIS_RESPONSE
        safety = True
    # Layer 2 — Off-topic detection
    elif _is_off_topic(payload.message):
        reply = random.choice(OFF_TOPIC_RESPONSES)
        safety = True
    else:
        safety = False
        messages = payload.conversation_history[-10:] + [{"role": "user", "content": payload.message}]
        journal_context = _get_journal_context(sb, uid)
        reply = call_seviyan(messages=messages, journal_context=journal_context)

    return {
        "reply":           reply,
        "safety_triggered": safety,
    }


def _get_journal_context(sb, user_id: str) -> str:
    try:
        res = app_db().table("journal_entries") \
            .select("content, created_at") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True).limit(3).execute()
        if not res.data:
            return ""
        return " | ".join(
            r["content"][:150] for r in res.data if r.get("content")
        )
    except Exception:
        return ""