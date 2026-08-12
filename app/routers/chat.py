import logging
import re
import random
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.dependencies import get_current_user, get_supabase
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


# ── GET conversations list ──────────────────────────────────────
@router.get("/conversations")
async def get_conversations(
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    try:
        res = sb.table("chat_sessions") \
            .select("id, title, created_at, updated_at") \
            .eq("user_id", str(user.id)) \
            .order("updated_at", desc=True) \
            .limit(20).execute()
        return {"conversations": res.data or []}
    except Exception as e:
        logger.error(f"get_conversations error: {e}")
        return {"conversations": []}


# ── POST create new conversation ────────────────────────────────
@router.post("/conversations")
async def create_conversation(
    payload: ConversationIn,
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    try:
        res = sb.table("chat_sessions").insert({
            "user_id": str(user.id),
            "title":   payload.title,
        }).execute()
        return {"conversation": res.data[0] if res.data else None}
    except Exception as e:
        logger.error(f"create_conversation error: {e}")
        return {"conversation": None}


# ── GET messages for a conversation ────────────────────────────
@router.get("/conversations/{session_id}/messages")
async def get_messages(
    session_id: str,
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    try:
        res = sb.table("chat_messages") \
            .select("id, role, content, created_at") \
            .eq("conversation_id", session_id) \
            .order("created_at", asc=True) \
            .execute()
        return {"messages": res.data or []}
    except Exception as e:
        logger.error(f"get_messages error: {e}")
        return {"messages": []}


# ── DELETE a conversation ───────────────────────────────────────
@router.delete("/conversations/{session_id}")
async def delete_conversation(
    session_id: str,
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    try:
        sb.table("chat_sessions") \
            .delete() \
            .eq("id", session_id) \
            .eq("user_id", str(user.id)) \
            .execute()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"delete_conversation error: {e}")
        return {"status": "error"}


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
        # Load session history from DB for context
        history = []
        if payload.session_id:
            try:
                hist_res = sb.table("chat_messages") \
                    .select("role, content") \
                    .eq("conversation_id", payload.session_id) \
                    .order("created_at", asc=True) \
                    .limit(20).execute()
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in (hist_res.data or [])
                ]
            except Exception:
                history = []

        messages = history + [{"role": "user", "content": payload.message}]
        journal_context = _get_journal_context(sb, uid)
        reply = call_seviyan(messages=messages, journal_context=journal_context)

    # Auto-create session if not provided
    session_id = payload.session_id
    if not session_id:
        try:
            # Use first 40 chars of user message as title
            title = payload.message[:40] + ("..." if len(payload.message) > 40 else "")
            sess_res = sb.table("chat_sessions").insert({
                "user_id": uid,
                "title":   title,
            }).execute()
            if sess_res.data:
                session_id = sess_res.data[0]["id"]
        except Exception as e:
            logger.error(f"Session create error: {e}")

    # Save both messages to DB
    if session_id:
        try:
            sb.table("chat_messages").insert([
                {"conversation_id": session_id, "role": "user",      "content": payload.message},
                {"conversation_id": session_id, "role": "assistant", "content": reply},
            ]).execute()
            # Update session updated_at
            sb.table("chat_sessions").update({
                "updated_at": "now()"
            }).eq("id", session_id).execute()
        except Exception as e:
            logger.error(f"Message save error: {e}")

    return {
        "reply":           reply,
        "session_id":      session_id,
        "safety_triggered": safety,
    }


def _get_journal_context(sb, user_id: str) -> str:
    try:
        res = sb.table("journal_entries") \
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