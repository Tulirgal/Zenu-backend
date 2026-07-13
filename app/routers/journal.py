from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.core.dependencies import AuthContext, require_auth
from app.schemas import JournalCreateInput, JournalUpdateInput
from app.services import journal_service

router = APIRouter(tags=["journal"])


@router.get("/api/journal")
async def journal_list(limit: int = 20, offset: int = 0, auth: AuthContext = Depends(require_auth)):
    return journal_service.list_entries(auth.user["id"], limit, offset)


@router.post("/api/journal", status_code=201)
async def journal_create(payload: JournalCreateInput, auth: AuthContext = Depends(require_auth)):
    return journal_service.create_entry(auth.user["id"], payload)


@router.put("/api/journal/{entry_id}")
async def journal_update(entry_id: str, payload: JournalUpdateInput, auth: AuthContext = Depends(require_auth)):
    return journal_service.update_entry(auth.user["id"], entry_id, payload)


@router.delete("/api/journal/{entry_id}", status_code=204)
async def journal_delete(entry_id: str, auth: AuthContext = Depends(require_auth)):
    journal_service.delete_entry(auth.user["id"], entry_id)
    return Response(status_code=204)
