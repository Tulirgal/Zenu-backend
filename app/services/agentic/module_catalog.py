"""
Canonical module definitions and base weights for ZenU.
base_weight: prior probability of being helpful (0-1).
tags: used for contextual signal matching.
duration_min: estimated session length.
"""

MODULES = [
    {"id": "breathing_box",        "name": "Box Breathing",          "base_weight": 0.80, "tags": ["quick", "anxiety", "focus"],          "duration_min": 3},
    {"id": "breathing_478",        "name": "4-7-8 Breathing",        "base_weight": 0.75, "tags": ["sleep", "anxiety", "calm"],           "duration_min": 4},
    {"id": "breathing_deep",       "name": "Deep Breathing",         "base_weight": 0.70, "tags": ["quick", "stress", "calm"],            "duration_min": 3},
    {"id": "breathing_cyclic",     "name": "Cyclic Sighing",         "base_weight": 0.65, "tags": ["stress", "quick", "release"],         "duration_min": 3},
    {"id": "journal_gratitude",    "name": "Gratitude Journal",      "base_weight": 0.72, "tags": ["reflection", "positive", "habit"],    "duration_min": 5},
    {"id": "arts_mandala",         "name": "Mandala Drawing",        "base_weight": 0.60, "tags": ["creative", "calm", "focus"],          "duration_min": 8},
    {"id": "arts_scribble",        "name": "Scribble Art",           "base_weight": 0.55, "tags": ["creative", "release", "play"],        "duration_min": 5},
    {"id": "meditation_jpmr",      "name": "JPMR Meditation",        "base_weight": 0.68, "tags": ["body", "relaxation", "sleep"],        "duration_min": 10},
    {"id": "meditation_imagery",   "name": "Guided Imagery",         "base_weight": 0.65, "tags": ["calm", "sleep", "body"],              "duration_min": 10},
    {"id": "meditation_grounding", "name": "Grounding 5-4-3-2-1",    "base_weight": 0.78, "tags": ["anxiety", "present", "quick"],        "duration_min": 4},
    {"id": "chatbot_seviyan",      "name": "Seviyan AI Companion",   "base_weight": 0.70, "tags": ["emotional", "talk", "support"],       "duration_min": 5},
    {"id": "mood_tracker",         "name": "Mood Check-In",          "base_weight": 0.60, "tags": ["reflection", "quick", "habit"],       "duration_min": 2},
    {"id": "bubble_simulation",    "name": "Burst It Out",           "base_weight": 0.50, "tags": ["play", "release", "quick"],           "duration_min": 3},
    {"id": "streak_garden",        "name": "Streak Garden",          "base_weight": 0.55, "tags": ["habit", "reflection", "positive"],    "duration_min": 2},
    {"id": "inner_compass",        "name": "Inner Compass",          "base_weight": 0.65, "tags": ["reflection", "support", "guidance"],  "duration_min": 5},
    {"id": "healing_garden",       "name": "Healing Garden",         "base_weight": 0.60, "tags": ["calm", "creative", "body"],           "duration_min": 7},
]

SITUATION_TAG_MAP = {
    "high_stress":    ["quick", "anxiety", "release", "grounding", "present"],
    "low_mood":       ["support", "talk", "positive", "reflection", "emotional"],
    "sleep_issues":   ["sleep", "calm", "body", "relaxation"],
    "creative_mode":  ["creative", "release", "play", "calm"],
    "habit_building": ["habit", "reflection", "streak", "positive"],
    "anxious":        ["anxiety", "quick", "grounding", "present", "calm"],
}
