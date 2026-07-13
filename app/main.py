from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import AppError
from app.routers.auth import router as auth_router
from app.routers.breathing import router as breathing_router
from app.routers.chat import router as chat_router
from app.routers.dashboard import router as dashboard_router
from app.routers.gratitude import router as gratitude_router
from app.routers.journal import router as journal_router
from app.routers.meditation import router as meditation_router
from app.routers.recommendation import router as recommendation_router
from app.routers.status import router as status_router

app = FastAPI(title="ZenU FastAPI Backend", version="0.2.0")

allowed_origins = settings.frontend_origins or ["*"]
dev_local_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$" if not settings.is_production else None
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=dev_local_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status, content={"error": exc.message, "details": exc.details})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"error": "Validation failed", "details": exc.errors()})


app.include_router(status_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(breathing_router)
app.include_router(meditation_router)
app.include_router(journal_router)
app.include_router(gratitude_router)
app.include_router(chat_router)
app.include_router(recommendation_router)
