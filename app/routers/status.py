from __future__ import annotations

from fastapi import APIRouter, Request

from app.services import status_service

router = APIRouter(tags=["status"])


@router.get("/health")
async def health():
    return status_service.health_status()


@router.get("/warmup")
async def warmup():
    return status_service.warmup_status()


@router.get("/api/status")
async def api_status():
    return status_service.api_status()


@router.get("/api/status/smtp")
async def smtp_status(request: Request):
    return status_service.smtp_status(request.headers.get("x-status-key"))
