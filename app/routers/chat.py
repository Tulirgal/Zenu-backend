import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.dependencies import get_current_user, get_supabase
from app.services.llm.nim_client import call_seviyan

logger = logging.getLogger("zenu.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])

CRISIS_PHRASES = [
    "hurt myself", "end it", "don't want to be here",
    "want to die", "kill myself", "give up on life",
    "no reason to live", "better off dead"
]

CRISIS_RESPONSE = (
    "I hear you, and I'm really glad you reached out. "
    "What you're feeling matters deeply. Please reach out to iCall right now — "
    "they're free, confidential, and available: 📞 9152987821. "
    "You can also text HELLO to 741741. You don't have to face this alone. 💙"
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

    # Crisis check — fast path before any LLM call
    if any(phrase in msg_lower for phrase in CRISIS_PHRASES):
        return {"reply": CRISIS_RESPONSE, "safety_triggered": True}

    # Build message history
    messages = payload.conversation_history[-10:] + [
        {"role": "user", "content": payload.message}
    ]

    # Get recent journal context for personalisation
    journal_context = _get_journal_context(sb, str(user.id))

    reply = call_seviyan(messages=messages, journal_context=journal_context)
    return {"reply": reply, "safety_triggered": False}


def _get_journal_context(sb, user_id: str) -> str:
    try:
        res = sb.table("journal_entries").select("content, created_at") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True).limit(3).execute()
        if not res.data:
            return ""
        return " | ".join(r["content"][:120] for r in res.data if r.get("content"))
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
