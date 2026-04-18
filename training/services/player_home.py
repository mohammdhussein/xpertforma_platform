from datetime import timedelta

from training.queries.player_home import (
    get_current_week_load,
    get_prev_week_load,
    get_today_insights,
    get_upcoming_sessions,
)
from training.queries.player_checkin import get_today_checkin


def get_readiness_label(score: int) -> str:
    if score >= 80:
        return "Ready to perform"
    if score >= 60:
        return "Good to train"
    if score >= 40:
        return "Train with caution"
    return "Consider rest today"


def get_load_status(ratio: float) -> str:
    if ratio < 1.3:
        return "safe"
    if ratio < 1.5:
        return "caution"
    return "danger"


def _compute_distance_delta_pct(curr_km, prev_km):
    if prev_km is None or float(prev_km) == 0:
        return None
    return round((float(curr_km) - float(prev_km)) / float(prev_km) * 100)


def _compute_load_ratio(acute, chronic):
    if not chronic:
        return None
    return round(acute / chronic, 2)


def build_player_home(player, today) -> dict:
    checkin = get_today_checkin(player, today)

    week_start = today - timedelta(days=today.weekday())
    prev_week_start = week_start - timedelta(weeks=1)

    curr_load = get_current_week_load(player, week_start)
    prev_load = get_prev_week_load(player, prev_week_start)
    insights = list(get_today_insights(player, today))
    sessions = list(get_upcoming_sessions(player, today))
    # --- readiness block ---
    if checkin is not None:
        readiness = {
            "score": checkin.readiness_score,
            "label": get_readiness_label(checkin.readiness_score),
            "sleep_hours": float(checkin.sleep_hours),
            "sleep_quality": checkin.sleep_quality,
            "mood": checkin.mood,
            "sore_zones": checkin.sore_zones,
            "submitted_today": True,
        }
    else:
        readiness = {
            "score": None,
            "label": None,
            "sleep_hours": None,
            "sleep_quality": None,
            "mood": None,
            "sore_zones": [],
            "submitted_today": False,
        }

    # --- upcoming sessions block ---
    upcoming_sessions = [
        {
            "id": str(s.session_id),
            "title": s.title,
            "session_date": s.session_date,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "intensity": s.intensity,
            "location": s.location,
            "squad_size": s.squad_size,
            "coach_note": s.coach_note,
        }
        for s in sessions
    ]

    # --- weekly progress block ---
    curr_km = float(curr_load.distance_km) if curr_load else 0.0
    prev_km = float(prev_load.distance_km) if prev_load else None
    acute = curr_load.acute_load if curr_load else 0
    chronic = curr_load.chronic_load if curr_load else 0
    load_ratio = _compute_load_ratio(acute, chronic)

    weekly_progress = {
        "distance_km": curr_km,
        "distance_km_prev": float(prev_km) if prev_km is not None else None,
        "distance_delta_pct": _compute_distance_delta_pct(curr_km, prev_km),
        "load_ratio": load_ratio,
        "acute_load": acute,
        "chronic_load": chronic,
        "load_status": get_load_status(load_ratio) if load_ratio is not None else "safe",
        "sessions_completed": curr_load.sessions_completed if curr_load else 0,
        "sessions_planned": curr_load.sessions_planned if curr_load else 0,
        "streak_days": curr_load.streak_days if curr_load else 0,
        "top_sprint_kmh": float(curr_load.top_sprint_kmh) if curr_load and curr_load.top_sprint_kmh else None,
        "top_sprint_pb_kmh": float(curr_load.top_sprint_pb_kmh) if curr_load and curr_load.top_sprint_pb_kmh else None,
    }

    # --- ai insights block ---
    ai_insights = [
        {"tag": insight.tag, "text": insight.text}
        for insight in insights
    ]

    return {
        "readiness": readiness,
        "upcoming_sessions": upcoming_sessions,
        "weekly_progress": weekly_progress,
        "ai_insights": ai_insights,
    }
