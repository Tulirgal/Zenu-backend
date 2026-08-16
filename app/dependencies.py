from fastapi import Depends
from supabase import Client
from pydantic import BaseModel

from app.core.dependencies import require_auth, AuthContext
from app.core.supabase import app_db, supabase_admin

class CurrentUser(BaseModel):
    id: str

async def get_current_user(auth: AuthContext = Depends(require_auth)) -> CurrentUser:
    return CurrentUser(id=str(auth.user.get("id")))

def get_supabase() -> Client:
    """Default admin client (public schema). Prefer get_app_db for product/rec data."""
    return supabase_admin

def get_app_db() -> Client:
    """Canonical ZenU application schema (app.*) — recommendation data plane."""
    return app_db()

def get_supabase_service_client() -> Client:
    return supabase_admin

def get_app_service_client() -> Client:
    """Service-role client scoped to app schema (nightly jobs, agentic writes)."""
    return app_db()
