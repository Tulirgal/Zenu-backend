from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings
from app.core.errors import AppError
from app.services.smtp_service import verify_smtp_connection


def health_status():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


def warmup_status():
    return {"status": "warming"}


def api_status():
    return {
        "status": "ok",
        "environment": settings.node_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def smtp_status(header_key: str | None):
    if settings.status_debug_key and settings.is_production:
        if header_key != settings.status_debug_key:
            raise AppError("Unauthorized", 401)

    return {"smtp": verify_smtp_connection()}
