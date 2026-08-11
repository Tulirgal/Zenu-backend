import os
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.dependencies import get_current_user, get_supabase
from app.services.llm.nim_client import call_seviyan_nim

logger = logging.getLogger("zenu.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessageIn(BaseModel):
    message: str
    conversation_history: list = []


@router.post("/message")
async def send_message(
    payload: ChatMessageIn,
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    # Build conversation messages
    messages = payload.conversation_history + [
        {"role": "user", "content": payload.message}
    ]

    # Fetch recent journal context for RAG personalization
    journal_context = await _get_journal_context(sb, str(user.id), payload.message)

    # Call NIM with Guardrails check
    try:
        # Crisis keyword pre-check (fast path before LLM call)
        crisis_keywords = ["hurt myself", "end it", "don't want to be here", "want to die", "give up on life"]
        msg_lower = payload.message.lower()
        if any(kw in msg_lower for kw in crisis_keywords):
            return {
                "reply": "I hear you, and I'm really glad you reached out. What you're feeling matters deeply. Please contact iCall right now — they're free and confidential: 9152987821. You don't have to face this alone.",
                "safety_triggered": True,
            }

        reply = call_seviyan_nim(messages=messages, journal_context=journal_context)
        return {"reply": reply, "safety_triggered": False}

    except Exception as e:
        logger.error(f"NIM chat error: {e}")
        return {"reply": "I'm having a little trouble connecting right now. Please try again in a moment.", "safety_triggered": False}


async def _get_journal_context(sb, user_id: str, query: str) -> str:
    """Pull last 3 journal entries as simple text context (basic RAG without vectors)."""
    try:
        res = sb.table("journal_entries").select("content, created_at") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True).limit(3).execute()
        if not res.data:
            return ""
        entries = [r["content"] for r in res.data if r.get("content")]
        return " | ".join(entries[:3])
    except Exception:
        return ""
