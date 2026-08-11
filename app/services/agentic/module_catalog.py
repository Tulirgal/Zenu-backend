"""
Canonical module definitions and base weights for ZenU.
base_weight: prior probability of being helpful (0-1).
tags: used for contextual signal matching.
duration_min: estimated session length.
"""

MODULES = [
    {
        "id": "breathing",
        "name": "Zen Breath Zone",
        "base_weight": 0.80,
        "tags": ["quick", "anxiety", "focus", "stress", "calm"],
        "duration_min": 3
    },
    {
        "id": "mindfulness",
        "name": "Mindfulness Studio",
        "base_weight": 0.72,
        "tags": ["calm", "body", "sleep", "relaxation", "grounding"],
        "duration_min": 8
    },
    {
        "id": "diary",
        "name": "My Diary",
        "base_weight": 0.60,
        "tags": ["reflection", "emotional", "habit", "support"],
        "duration_min": 5
    },
    {
        "id": "journal_gratitude",
        "name": "Gratitude Journal",
        "base_weight": 0.72,
        "tags": ["reflection", "positive", "habit", "emotional"],
        "duration_min": 5
    },
    {
        "id": "doodle_dreams",
        "name": "Doodle Dreams Studio",
        "base_weight": 0.62,
        "tags": ["creative", "calm", "focus", "play"],
        "duration_min": 8
    },
    {
        "id": "bubble_canvas",
        "name": "Bubble Canvas",
        "base_weight": 0.55,
        "tags": ["play", "release", "quick", "stress"],
        "duration_min": 3
    },
    {
        "id": "burst_it_out",
        "name": "Burst It OUT",
        "base_weight": 0.58,
        "tags": ["release", "stress", "quick", "emotional"],
        "duration_min": 3
    },
    {
        "id": "scribble_pad",
        "name": "Scribble Pad",
        "base_weight": 0.55,
        "tags": ["creative", "release", "play", "calm"],
        "duration_min": 5
    },
    {
        "id": "chatbot_seviyan",
        "name": "Seviyan",
        "base_weight": 0.75,
        "tags": ["emotional", "talk", "support", "anxiety"],
        "duration_min": 5
    },
    {
        "id": "healing_garden",
        "name": "Healing Garden",
        "base_weight": 0.60,
        "tags": ["calm", "habit", "positive", "body"],
        "duration_min": 6
    },
    {
        "id": "inner_compass",
        "name": "Inner Compass",
        "base_weight": 0.65,
        "tags": ["reflection", "guidance", "support", "habit"],
        "duration_min": 5
    },
]

SITUATION_TAG_MAP = {
    "high_stress":    ["quick", "anxiety", "release", "stress", "grounding"],
    "low_mood":       ["support", "talk", "positive", "reflection", "emotional"],
    "sleep_issues":   ["sleep", "calm", "body", "relaxation"],
    "creative_mode":  ["creative", "release", "play", "calm"],
    "habit_building": ["habit", "reflection", "positive", "guidance"],
    "anxious":        ["anxiety", "quick", "grounding", "calm", "support"],
}
