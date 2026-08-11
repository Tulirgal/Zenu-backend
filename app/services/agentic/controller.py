"""
Agentic Decision Controller — orchestrates the full recommendation pipeline:
  cached features → X-Algorithm ranking → post-filter → log → return
"""

import logging
from datetime import datetime, timedelta, timezone
from supabase import Client
from app.services.agentic.feature_extractor import FeatureExtractor
from app.services.agentic.x_algorithm import XAlgorithmRanker

logger = logging.getLogger("zenu.controller")


class AgenticController:

    def __init__(self, supabase: Client, user_id: str):
        self.sb  = supabase
        self.uid = user_id

    def get_recommendations(self, top_n: int = 3) -> dict:
        features = self._load_cached_features() or self._compute_live_features()
        history  = self._load_engagement_history()
        overrides = self._load_weight_overrides()

        ranker = XAlgorithmRanker(
            features=features,
            user_engagement_history=history,
            weight_overrides=overrides,
        )
        ranked   = ranker.rank(top_n=top_n * 2)
        filtered = self._post_filter(ranked, features, max_results=top_n)

        self._log_recommendation(filtered, features)

        return {
            "recommendations": filtered,
            "context": {
                "avg_mood_7d":   features.get("avg_mood_7d"),
                "dominant_tone": features.get("dominant_tone"),
                "time_of_day":   features.get("time_of_day"),
                "stress_level":  self._stress_label(features.get("pss_norm", 0.5)),
            }
        }

    def _load_cached_features(self) -> dict | None:
        try:
            res = self.sb.table("user_feature_vectors").select("*") \
                .eq("user_id", self.uid).limit(1).execute()
            if not res.data:
                return None
            row = res.data[0]
            computed = row.get("last_computed_at")
            if computed:
                dt = datetime.fromisoformat(computed.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - dt < timedelta(hours=12):
                    return {
                        "avg_mood_7d":          row.get("avg_mood_7d", 0.5),
                        "pss_norm":             row.get("pss_norm", 0.5),
                        "dominant_tone":        row.get("dominant_tone", "neutral"),
                        "engagement_rate":      row.get("engagement_rate", 0.5),
                        "preferred_time_slots": row.get("preferred_time_slots", ["any"]),
                        "streak_days":          row.get("streak_days", 0),
                        "time_of_day":          FeatureExtractor._time_of_day_bucket(),
                    }
        except Exception:
            pass
        return None

    def _compute_live_features(self) -> dict:
        return FeatureExtractor(self.sb, self.uid).extract()

    def _load_engagement_history(self) -> list:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        try:
            res = self.sb.table("engagement_events") \
                .select("module_id, event_type, occurred_at") \
                .eq("user_id", self.uid).gte("occurred_at", cutoff) \
                .order("occurred_at", desc=True).execute()
            latest: dict = {}
            for event in (res.data or []):
                mid = event["module_id"]
                if mid not in latest:
                    occ = datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00"))
                    days = (datetime.now(timezone.utc) - occ).total_seconds() / 86400
                    latest[mid] = {
                        "module_id":      mid,
                        "event_type":     event["event_type"],
                        "days_since_last": round(days, 2),
                    }
            return list(latest.values())
        except Exception:
            return []

    def _load_weight_overrides(self) -> dict:
        try:
            res = self.sb.table("module_weight_overrides") \
                .select("module_id, weight_delta") \
                .eq("user_id", self.uid).execute()
            return {r["module_id"]: r["weight_delta"] for r in (res.data or [])}
        except Exception:
            return {}

    def _post_filter(self, ranked: list, features: dict, max_results: int) -> list:
        preferred = features.get("preferred_time_slots", ["any"])
        current   = features.get("time_of_day", "any")
        in_pref   = current in preferred or "any" in preferred

        result, seen_tags = [], set()
        for module in ranked:
            if len(result) >= max_results:
                break
            primary = module["tags"][0] if module["tags"] else "general"
            if primary in seen_tags:
                continue
            if not in_pref and module["duration_min"] > 8:
                continue
            result.append(module)
            seen_tags.add(primary)

        # Fill if diversity filter was too aggressive
        if len(result) < max_results:
            for module in ranked:
                if module not in result:
                    result.append(module)
                if len(result) >= max_results:
                    break

        return result

    def _log_recommendation(self, modules: list, features: dict):
        try:
            self.sb.table("recommendation_log").insert({
                "user_id":        self.uid,
                "modules_offered": modules,
                "context_snapshot": {
                    "avg_mood_7d":   features.get("avg_mood_7d"),
                    "pss_norm":      features.get("pss_norm"),
                    "time_of_day":   features.get("time_of_day"),
                    "dominant_tone": features.get("dominant_tone"),
                },
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to log recommendation: {e}")

    @staticmethod
    def _stress_label(pss_norm: float) -> str:
        if pss_norm < 0.33:
            return "high"
        elif pss_norm < 0.66:
            return "moderate"
        return "low"
