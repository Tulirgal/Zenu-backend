from __future__ import annotations

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class SignUpInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    fullName: str | None = Field(default=None, max_length=120)
    username: str | None = Field(default=None, min_length=2, max_length=32)


class SignInInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshInput(BaseModel):
    refreshToken: str | None = None


class GoogleSessionInput(BaseModel):
    ticket: str = Field(min_length=16, max_length=256)


class ForgotPasswordInput(BaseModel):
    email: EmailStr


class ResetPasswordInput(BaseModel):
    email: EmailStr
    token: str = Field(min_length=1)
    password: str = Field(min_length=8)


class ActivityInput(BaseModel):
    module: str
    payload: dict[str, Any] | None = None


class PSSInput(BaseModel):
    scores: list[int]


class BreathingSessionInput(BaseModel):
    patternId: str
    durationSeconds: int = Field(gt=0)
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=500)


class MeditationSessionInput(BaseModel):
    meditationId: str
    durationSeconds: int = Field(gt=0)


class JournalCreateInput(BaseModel):
    mood: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=120)
    content: str = Field(min_length=1)


class JournalUpdateInput(BaseModel):
    mood: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=120)
    content: str | None = Field(default=None, min_length=1)


class GratitudeCreateInput(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    content: str = Field(min_length=1, max_length=5000)


class ChatInput(BaseModel):
    message: str = Field(min_length=1)
    conversationId: str | None = None
