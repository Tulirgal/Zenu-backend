from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from app.dependencies import get_current_user, get_supabase
import logging

logger = logging.getLogger("zenu.healing_garden")
router = APIRouter(prefix="/api/healing-garden", tags=["healing-garden"])


class TaskIn(BaseModel):
    name: str


@router.get("/tasks")
async def get_tasks(
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    try:
        res = sb.table("healing_garden_tasks") \
            .select("*") \
            .eq("user_id", str(user.id)) \
            .order("created_at", desc=False) \
            .execute()
        return {"tasks": res.data or []}
    except Exception as e:
        logger.error(f"get_tasks error: {e}")
        return {"tasks": []}


@router.post("/tasks")
async def create_task(
    payload: TaskIn,
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    try:
        res = sb.table("healing_garden_tasks").insert({
            "user_id": str(user.id),
            "name":    payload.name.strip()[:80],
        }).execute()
        return {"task": res.data[0] if res.data else None}
    except Exception as e:
        logger.error(f"create_task error: {e}")
        return {"task": None}


@router.patch("/tasks/{task_id}/complete")
async def complete_task(
    task_id: str,
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    try:
        res = sb.table("healing_garden_tasks").update({
            "completed":    True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", task_id).eq("user_id", str(user.id)).execute()
        return {"task": res.data[0] if res.data else None}
    except Exception as e:
        logger.error(f"complete_task error: {e}")
        return {"task": None}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    user=Depends(get_current_user),
    sb=Depends(get_supabase),
):
    try:
        sb.table("healing_garden_tasks") \
            .delete() \
            .eq("id", task_id) \
            .eq("user_id", str(user.id)) \
            .execute()
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"delete_task error: {e}")
        return {"status": "error"}
