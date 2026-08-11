from fastapi import Depends
from supabase import Client
from pydantic import BaseModel

from app.core.dependencies import require_auth, AuthContext
from app.core.supabase import supabase_admin

class CurrentUser(BaseModel):
    id: str

async def get_current_user(auth: AuthContext = Depends(require_auth)) -> CurrentUser:
    return CurrentUser(id=str(auth.user.get("id")))

def get_supabase() -> Client:
    return supabase_admin

def get_supabase_service_client() -> Client:
    return supabase_admin
