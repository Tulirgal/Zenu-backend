from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

import google.generativeai as genai

from app.core.config import settings

MODULE_SLUGS = {
    "breathing",
    "meditation",
    "journal",
    "gratitude",
    "mandala",
    "bubble",
    "burst",
    "scribble",
    "chatbot",
    "garden",
    "compass",
}


def parse_iso_date(value: str) -> datetime:
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def format_day_key(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d")


def compute_plant_stage(streak: int) -> str:
    if streak >= 14:
        return "tree"
    if streak >= 5:
        return "sapling"
    return "seedling"


def get_gemini_model():
    if not settings.gemini_api_key:
        return None
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(settings.gemini_model)


def extract_json_object(text: str) -> dict[str, Any] | None:
    first = text.find("{")
    last = text.rfind("}")
    if first < 0 or last < 0 or first >= last:
        return None
    try:
        return json.loads(text[first : last + 1])
    except Exception:
        return None


def heuristic_gratitude_score(content: str) -> int:
    lower = content.lower()
    tokens = [
        "thank",
        "grateful",
        "appreciate",
        "blessed",
        "support",
        "kind",
        "learned",
        "growth",
        "family",
        "friend",
        "help",
    ]
    token_hits = sum(1 for token in tokens if token in lower)
    length_boost = min(2, math.floor(len(content.strip()) / 180))
    return max(3, min(10, 4 + token_hits + length_boost))


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
