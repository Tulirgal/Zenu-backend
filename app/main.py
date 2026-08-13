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
from app.routers import signals
from app.tasks.nightly_autoresearch import scheduler

app = FastAPI(title="ZenU FastAPI Backend", version="0.2.0")

import os

ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("FRONTEND_URL", "http://localhost:3000").split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,          # never use allow_origins=["*"] when credentials=True
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Accept", "Origin"],
    expose_headers=["Set-Cookie"],
    max_age=600,
)


@app.options("/{rest_of_path:path}")
async def preflight_handler(request: Request, rest_of_path: str):
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, Accept, Origin",
        },
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
app.include_router(signals.router)
from app.routers import healing_garden
app.include_router(healing_garden.router)

@app.on_event("startup")
async def startup_event():
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown(wait=False)
