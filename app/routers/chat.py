from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import AuthContext, require_auth
from app.schemas import ChatInput
from app.services import chat_service

router = APIRouter(tags=["chat"])


@router.get("/api/chat/conversations")
async def chat_conversations(auth: AuthContext = Depends(require_auth)):
    return chat_service.list_conversations(auth.user["id"])


@router.get("/api/chat/conversations/{conversation_id}/messages")
async def chat_messages(conversation_id: str, auth: AuthContext = Depends(require_auth)):
    return chat_service.get_messages(auth.user["id"], conversation_id)


@router.post("/api/chat/messages", status_code=201)
async def chat_send(payload: ChatInput, auth: AuthContext = Depends(require_auth)):
    return chat_service.send_message(auth.user["id"], payload)
