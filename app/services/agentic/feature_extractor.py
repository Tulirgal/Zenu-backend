"""
Builds a normalized feature vector [0.0, 1.0] for a given user
from their Supabase signal tables.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from supabase import Client
from app.services.agentic.tone_analyzer import ToneAnalyzer


class FeatureExtractor:

    def __init__(self, supabase: Client, user_id: str):
        self.sb = supabase
        self.uid = user_id

    def extract(self) -> dict:
        return {
            "avg_mood_7d":          self._avg_mood_7d(),
            "pss_norm":             self._latest_pss_norm(),
            "dominant_tone":        self._dominant_journal_tone(),
            "engagement_rate":      self._engagement_rate(),
            "preferred_time_slots": self._preferred_time_slots(),
            "streak_days":          self._streak_days(),
            "time_of_day":          self._time_of_day_bucket(),
        }

    def _avg_mood_7d(self) -> float:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        try:
            res = self.sb.table("mood_logs").select("mood_score") \
                .eq("user_id", self.uid).gte("logged_at", cutoff).execute()
            scores = [r["mood_score"] for r in (res.data or [])]
            if not scores:
                return 0.5
            return round((sum(scores) / len(scores) - 1) / 9.0, 4)
        except Exception:
            return 0.5

    def _latest_pss_norm(self) -> float:
        try:
            res = self.sb.table("pss_scores").select("raw_score") \
                .eq("user_id", self.uid).order("assessed_at", desc=True).limit(1).execute()
            if not res.data:
                return 0.5
            return round(1.0 - res.data[0]["raw_score"] / 40.0, 4)
        except Exception:
            return 0.5

    def _dominant_journal_tone(self) -> str:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        try:
            # Try journal_entries table — adjust table name if different in your schema
            res = self.sb.table("journal_entries").select("content") \
                .eq("user_id", self.uid).gte("created_at", cutoff).limit(10).execute()
            texts = [r["content"] for r in (res.data or []) if r.get("content")]
            return ToneAnalyzer().dominant_tone(texts)
        except Exception:
            return "neutral"

    def _engagement_rate(self) -> float:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        try:
            res = self.sb.table("engagement_events").select("event_type") \
                .eq("user_id", self.uid).gte("occurred_at", cutoff).execute()
            events = res.data or []
            if not events:
                return 0.5
            completed = sum(1 for e in events if e["event_type"] == "completed")
            return round(min(completed / len(events), 1.0), 4)
        except Exception:
            return 0.5

    def _preferred_time_slots(self) -> list:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        try:
            res = self.sb.table("engagement_events").select("occurred_at") \
                .eq("user_id", self.uid).eq("event_type", "completed") \
                .gte("occurred_at", cutoff).execute()
            buckets: dict = {}
            for event in (res.data or []):
                from datetime import timezone, timedelta
                IST = timezone(timedelta(hours=5, minutes=30))
                hour = datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00")).astimezone(IST).hour
                b = self._hour_to_bucket(hour)
                buckets[b] = buckets.get(b, 0) + 1
            if not buckets:
                return ["any"]
            max_count = max(buckets.values())
            return [b for b, c in buckets.items() if c >= max_count * 0.7]
        except Exception:
            return ["any"]

    def _streak_days(self) -> int:
        try:
            res = self.sb.table("user_feature_vectors").select("streak_days") \
                .eq("user_id", self.uid).limit(1).execute()
            if res.data:
                return res.data[0].get("streak_days", 0)
            return 0
        except Exception:
            return 0

    @staticmethod
    def _time_of_day_bucket() -> str:
        from datetime import timezone, timedelta
        IST = timezone(timedelta(hours=5, minutes=30))
        hour = datetime.now(IST).hour
        return FeatureExtractor._hour_to_bucket(hour)

    @staticmethod
    def _hour_to_bucket(hour: int) -> str:
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"
