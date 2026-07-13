from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.supabase import app_db
from app.services.common import clamp01, format_day_key, parse_iso_date
from app.services.dashboard_service import get_streak_summary


def _get_pss_trend(scores: list[float]) -> str:
    if len(scores) < 4:
        return "unknown"

    current_window = scores[:3]
    previous_window = scores[3:6]
    if not previous_window:
        return "unknown"

    current_avg = sum(current_window) / len(current_window)
    previous_avg = sum(previous_window) / len(previous_window)
    delta = current_avg - previous_avg

    if delta <= -0.7:
        return "improving"
    if delta >= 0.7:
        return "worsening"
    return "stable"


def _confidence_from_signals(signals: dict) -> float:
    confidence = 0.35
    if signals["pss"]["latestAverage"] is not None:
        confidence += 0.25
    if signals["activity"]["totalEventsLast14Days"] > 0:
        confidence += 0.25
    if signals["streak"]["lastActivity"]:
        confidence += 0.15
    return clamp01(confidence)


def get_recommendations(user_id: str):
    fourteen_days_ago = datetime.now(timezone.utc) - timedelta(days=14)

    pss_res = (
        app_db()
        .table("pss_assessments")
        .select("average_score,flagged,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(8)
        .execute()
    )

    activity_res = (
        app_db()
        .table("activity_logs")
        .select("module,occurred_at")
        .eq("user_id", user_id)
        .gte("occurred_at", fourteen_days_ago.isoformat())
        .order("occurred_at", desc=True)
        .execute()
    )

    streak = get_streak_summary(user_id)

    pss_rows = pss_res.data or []
    activity_rows = activity_res.data or []

    pss_scores = [float(row.get("average_score") or 0) for row in pss_rows]
    module_frequency: dict[str, int] = {}
    for row in activity_rows:
        module = str(row.get("module") or "unknown")
        module_frequency[module] = module_frequency.get(module, 0) + 1

    distinct_days = {
        format_day_key(parse_iso_date(row.get("occurred_at")))
        for row in activity_rows
        if row.get("occurred_at")
    }

    signals = {
        "pss": {
            "latestAverage": pss_scores[0] if pss_scores else None,
            "latestFlagged": bool((pss_rows[0] if pss_rows else {}).get("flagged")),
            "trend": _get_pss_trend(pss_scores),
            "sampleCount": len(pss_scores),
        },
        "activity": {
            "totalEventsLast14Days": len(activity_rows),
            "distinctDaysLast14Days": len(distinct_days),
            "mostRecentEventAt": (activity_rows[0] if activity_rows else {}).get("occurred_at"),
            "moduleFrequency": module_frequency,
        },
        "streak": streak,
    }

    candidates = [
        ("breathing", 4),
        ("meditation", 8),
        ("journal", 10),
        ("chatbot", 6),
        ("bubble", 3),
        ("scribble", 6),
        ("mandala", 8),
        ("gratitude", 5),
        ("compass", 7),
        ("burst", 3),
    ]

    score_card: dict[str, dict] = {module: {"score": 0.3, "reasons": []} for module, _ in candidates}

    def add_score(module: str, delta: float, code: str, message: str):
        if module not in score_card:
            return
        score_card[module]["score"] += delta
        score_card[module]["reasons"].append({"code": code, "message": message})

    latest_stress = signals["pss"]["latestAverage"]
    stress_high = latest_stress is not None and latest_stress >= 7
    stress_medium = latest_stress is not None and 4 <= latest_stress < 7

    most_recent = signals["activity"]["mostRecentEventAt"]
    long_inactivity = True
    if most_recent:
        elapsed = datetime.now(timezone.utc) - parse_iso_date(most_recent)
        long_inactivity = elapsed.total_seconds() >= 60 * 60 * 48

    low_streak = signals["streak"]["currentStreak"] < 3
    strong_streak = signals["streak"]["currentStreak"] >= 7

    if stress_high:
        add_score("breathing", 0.45, "high_stress_support", "High stress detected; breathing can downshift your nervous system quickly.")
        add_score("meditation", 0.4, "high_stress_support", "High stress detected; guided meditation helps with sustained regulation.")
        add_score("journal", 0.35, "high_stress_support", "High stress detected; journaling can externalize and organize thoughts.")
    elif stress_medium:
        add_score("breathing", 0.3, "medium_stress_support", "Moderate stress detected; short breathing sessions can prevent escalation.")
        add_score("gratitude", 0.22, "medium_stress_support", "Moderate stress detected; gratitude can shift cognitive framing.")

    if long_inactivity:
        add_score("bubble", 0.28, "re_engagement", "Activity has dipped; quick low-effort tools can help restart momentum.")
        add_score("breathing", 0.25, "re_engagement", "A short breathing reset is a simple first step back into routine.")
        add_score("scribble", 0.2, "re_engagement", "Creative decompression can make re-engagement easier.")

    if low_streak:
        add_score("breathing", 0.2, "streak_recovery", "Current streak is low; short repeatable practices improve consistency.")
        add_score("burst", 0.12, "streak_recovery", "Quick wins can rebuild habit confidence after missed days.")

    if strong_streak:
        add_score("journal", 0.18, "streak_maintenance", "Your streak is strong; reflection helps convert consistency into insight.")
        add_score("compass", 0.18, "streak_maintenance", "Your streak is strong; deeper exercises can sustain growth.")

    trend = signals["pss"]["trend"]
    if trend == "improving":
        add_score("gratitude", 0.18, "positive_progress_maintain", "Recent stress trend is improving; gratitude can help preserve progress.")
        add_score("journal", 0.14, "positive_progress_maintain", "Recent progress suggests reflection can reinforce what is working.")
    elif trend == "worsening":
        add_score("breathing", 0.26, "worsening_trend_support", "Stress trend is worsening; start with immediate physiological regulation.")
        add_score("meditation", 0.24, "worsening_trend_support", "Stress trend is worsening; guided practice can reduce rumination load.")
        add_score("chatbot", 0.18, "worsening_trend_support", "Stress trend is worsening; conversation can structure next actions.")

    if module_frequency:
        top_module = sorted(module_frequency.items(), key=lambda x: x[1], reverse=True)[0][0]
        if top_module in score_card:
            add_score(top_module, -0.15, "diversify", "Diversifying practices may improve resilience versus repeating one tool only.")

    for module, _ in candidates:
        add_score(module, 0.06, "balanced_wellness", "Balanced support plan to combine regulation, reflection, and expression.")

    confidence = _confidence_from_signals(signals)
    recommendations = []
    for module, minutes in candidates:
        card = score_card[module]
        recommendations.append(
            {
                "module": module,
                "score": round(clamp01(card["score"]), 3),
                "confidence": confidence,
                "estimatedDurationMin": minutes,
                "reasons": card["reasons"],
            }
        )

    recommendations.sort(key=lambda x: x["score"], reverse=True)

    return {"generatedAt": datetime.now(timezone.utc).isoformat(), "signals": signals, "recommendations": recommendations[:4]}
