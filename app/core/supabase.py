from __future__ import annotations

from supabase import Client, create_client

from app.core.config import settings

if not settings.supabase_url or not settings.supabase_anon_key or not settings.supabase_service_role_key:
    raise RuntimeError("SUPABASE_URL, SUPABASE_ANON_KEY and SUPABASE_SERVICE_ROLE_KEY are required")

supabase_anon: Client = create_client(settings.supabase_url, settings.supabase_anon_key)
supabase_admin: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)


def app_db():
    return supabase_admin.schema("app")
