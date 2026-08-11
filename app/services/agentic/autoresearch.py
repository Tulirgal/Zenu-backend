"""
Autoresearch Loop — Nightly weight refinement.

Inspired by iterative feedback-loop architectures similar to how
recommendation systems retrain on recent interaction data.

Runs nightly at 2 AM UTC. For each active user:
1. Pulls last 24h recommendation logs
2. Computes per-module acceptance rates
3. Nudges weight_delta up/down via gradient update
4. Refreshes user_feature_vectors cache
"""

import logging
from datetime import datetime, timedelta, timezone
from supabase import Client

logger = logging.getLogger("zenu.autoresearch")

LEARNING_RATE = 0.05
MAX_DELTA     = 0.25
MIN_EVENTS    = 3


class AutoresearchLoop:

    def __init__(self, supabase: Client):
        self.sb = supabase

    def run(self):
        logger.info("Autoresearch loop starting...")
        user_ids = self._get_active_user_ids()
        success, failed = 0, 0
        for uid in user_ids:
            try:
                self._refine_user(uid)
                success += 1
            except Exception as e:
                logger.error(f"Autoresearch failed for user {uid}: {e}")
                failed += 1
        logger.info(f"Autoresearch complete. Success={success} Failed={failed}")

    def _get_active_user_ids(self) -> list:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        try:
            res = self.sb.table("engagement_events").select("user_id") \
                .gte("occurred_at", cutoff).execute()
            return list({r["user_id"] for r in (res.data or [])})
        except Exception:
            return []

    def _refine_user(self, user_id: str):
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        logs = self.sb.table("recommendation_log") \
            .select("modules_offered, modules_accepted") \
            .eq("user_id", user_id) \
            .gte("recommended_at", cutoff).execute().data or []

        if not logs:
            self._refresh_feature_vector(user_id)
            return

        offered_count:  dict = {}
        accepted_count: dict = {}

        for log in logs:
            for m in (log.get("modules_offered") or []):
                mid = m["module_id"]
                offered_count[mid] = offered_count.get(mid, 0) + 1
            for m in (log.get("modules_accepted") or []):
                mid = m["module_id"]
                accepted_count[mid] = accepted_count.get(mid, 0) + 1

        for mid, offered in offered_count.items():
            if offered < MIN_EVENTS:
                continue

            acceptance_rate = accepted_count.get(mid, 0) / offered

            if acceptance_rate > 0.55:
                gradient = LEARNING_RATE * (acceptance_rate - 0.5)
            elif acceptance_rate < 0.25:
                gradient = -LEARNING_RATE * (0.3 - acceptance_rate)
            else:
                continue  # neutral band — no update

            try:
                existing = self.sb.table("module_weight_overrides") \
                    .select("weight_delta, confidence") \
                    .eq("user_id", user_id).eq("module_id", mid) \
                    .limit(1).execute().data
            except Exception:
                existing = []

            current_delta = existing[0]["weight_delta"] if existing else 0.0
            current_conf  = existing[0]["confidence"]   if existing else 0.5

            new_delta = max(-MAX_DELTA, min(MAX_DELTA, current_delta + gradient))
            new_conf  = min(current_conf + 0.04, 1.0)

            self.sb.table("module_weight_overrides").upsert({
                "user_id":      user_id,
                "module_id":    mid,
                "weight_delta": new_delta,
                "confidence":   new_conf,
                "updated_at":   datetime.now(timezone.utc).isoformat(),
            }).execute()

        self._refresh_feature_vector(user_id)

    def _refresh_feature_vector(self, user_id: str):
        from app.services.agentic.feature_extractor import FeatureExtractor
        features = FeatureExtractor(self.sb, user_id).extract()
        self.sb.table("user_feature_vectors").upsert({
            "user_id":              user_id,
            "avg_mood_7d":          features["avg_mood_7d"],
            "pss_norm":             features["pss_norm"],
            "dominant_tone":        features["dominant_tone"],
            "engagement_rate":      features["engagement_rate"],
            "preferred_time_slots": features["preferred_time_slots"],
            "streak_days":          features["streak_days"],
            "last_computed_at":     datetime.now(timezone.utc).isoformat(),
        }).execute()
