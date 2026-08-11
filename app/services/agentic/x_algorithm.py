"""
X-Algorithm Multi-Signal Ranker for ZenU.

Inspired by Twitter/X's open-source recommendation architecture.
Uses weighted multi-signal scoring with candidate generation → ranking → filtering.

Score formula:
  score = (
      W_mood   * mood_relevance   +
      W_pss    * pss_relevance    +
      W_tone   * tone_relevance   +
      W_engage * engagement_affinity +
      W_time   * time_fit         +
      W_streak * streak_bonus     +
      W_base   * module.base_weight
  ) * recency_decay * (1 + learned_delta)
"""

from typing import Optional
from app.services.agentic.module_catalog import MODULES

DEFAULT_WEIGHTS = {
    "mood":   0.28,
    "pss":    0.20,
    "tone":   0.15,
    "engage": 0.18,
    "time":   0.10,
    "streak": 0.05,
    "base":   0.04,
}


class XAlgorithmRanker:

    def __init__(
        self,
        features: dict,
        user_engagement_history: list,
        weight_overrides: Optional[dict] = None,
        signal_weights: Optional[dict] = None,
    ):
        self.f = features
        self.history = {e["module_id"]: e for e in user_engagement_history}
        self.weight_overrides = weight_overrides or {}
        self.W = {**DEFAULT_WEIGHTS, **(signal_weights or {})}

    def rank(self, top_n: int = 3) -> list:
        scored = []
        for module in MODULES:
            score = self._score(module)
            scored.append({
                "module_id":    module["id"],
                "name":         module["name"],
                "rank_score":   round(score, 4),
                "duration_min": module["duration_min"],
                "tags":         module["tags"],
            })
        scored.sort(key=lambda x: x["rank_score"], reverse=True)
        return scored[:top_n]

    def _score(self, module: dict) -> float:
        f    = self.f
        W    = self.W
        mid  = module["id"]
        tags = set(module["tags"])

        mood_rel   = self._mood_relevance(tags, f.get("avg_mood_7d", 0.5))
        pss_rel    = self._pss_relevance(tags, f.get("pss_norm", 0.5))
        tone_rel   = self._tone_relevance(tags, f.get("dominant_tone", "neutral"))
        engage_aff = self._engagement_affinity(mid)
        time_fit   = self._time_fit(tags, f.get("time_of_day", "any"))
        streak_bon = self._streak_bonus(tags, f.get("streak_days", 0))
        base_w     = module["base_weight"]
        decay      = self._recency_decay(mid)

        raw = (
            W["mood"]   * mood_rel   +
            W["pss"]    * pss_rel    +
            W["tone"]   * tone_rel   +
            W["engage"] * engage_aff +
            W["time"]   * time_fit   +
            W["streak"] * streak_bon +
            W["base"]   * base_w
        )

        # Apply learned weight delta from Autoresearch loop
        delta = self.weight_overrides.get(mid, 0.0)
        final = raw * decay + delta
        return min(max(final, 0.0), 1.0)

    def _mood_relevance(self, tags: set, avg_mood: float) -> float:
        if avg_mood < 0.35:
            preferred = {"anxiety", "support", "calm", "quick", "release", "grounding"}
        elif avg_mood > 0.65:
            preferred = {"creative", "habit", "reflection", "positive", "play"}
        else:
            preferred = {"stress", "reflection", "body", "focus"}
        return min(len(tags & preferred) / 2.5, 1.0)

    def _pss_relevance(self, tags: set, pss_norm: float) -> float:
        if pss_norm < 0.35:
            preferred = {"quick", "grounding", "release", "anxiety", "present"}
        else:
            preferred = {"body", "sleep", "habit", "creative", "reflection"}
        return min(len(tags & preferred) / 2.5, 1.0)

    def _tone_relevance(self, tags: set, tone: str) -> float:
        tone_map = {
            "negative": {"support", "talk", "release", "calm", "emotional"},
            "anxious":  {"anxiety", "grounding", "quick", "body", "present"},
            "positive": {"habit", "creative", "reflection", "positive", "play"},
            "neutral":  {"reflection", "body", "calm", "focus"},
        }
        preferred = tone_map.get(tone, set())
        return min(len(tags & preferred) / 2.5, 1.0)

    def _engagement_affinity(self, module_id: str) -> float:
        if module_id not in self.history:
            return 0.5
        event = self.history[module_id]
        et = event.get("event_type", "")
        if et == "completed":
            return min(0.6 + event.get("completion_rate", 0.4) * 0.4, 1.0)
        elif et == "skipped":
            return 0.15
        elif et == "abandoned":
            return 0.25
        return 0.5

    def _time_fit(self, tags: set, time_of_day: str) -> float:
        time_map = {
            "morning":   {"focus", "habit", "reflection", "quick", "positive"},
            "afternoon": {"quick", "stress", "focus", "play"},
            "evening":   {"calm", "creative", "reflection", "body", "emotional"},
            "night":     {"sleep", "calm", "body", "anxiety", "grounding"},
        }
        preferred = time_map.get(time_of_day, set())
        return min(len(tags & preferred) / 2.0, 1.0)

    def _streak_bonus(self, tags: set, streak_days: int) -> float:
        if streak_days >= 7 and "habit" in tags:
            return 1.0
        elif streak_days >= 3 and "reflection" in tags:
            return 0.6
        elif streak_days >= 1 and "positive" in tags:
            return 0.3
        return 0.0

    def _recency_decay(self, module_id: str) -> float:
        if module_id not in self.history:
            return 1.0
        days = self.history[module_id].get("days_since_last", 999)
        if days < 0.5:
            return 0.3
        elif days < 1:
            return 0.5
        elif days < 3:
            return 0.75
        return 1.0
