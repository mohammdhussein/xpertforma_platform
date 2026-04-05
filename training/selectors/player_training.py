from datetime import date as dt_date, datetime

from django.utils.dateparse import parse_date
from rest_framework.exceptions import ParseError

from training.models import PlayerSessionProgress, TrainingPlanPlayer, TrainingSession
from training.statuses import is_completed_player_session_status, normalize_player_session_status


def _duration_min(start_time, end_time):
    if not start_time or not end_time:
        return 0
    start_dt = datetime.combine(dt_date.today(), start_time)
    end_dt = datetime.combine(dt_date.today(), end_time)
    return max(int((end_dt - start_dt).total_seconds() // 60), 0)


def build_player_training_day_payload(player_user, *, date_str):
    selected_date = parse_date(date_str) if date_str else dt_date.today()
    if not selected_date:
        raise ParseError(detail="Invalid date format. Use YYYY-MM-DD.")

    assigned_plans = TrainingPlanPlayer.objects.filter(player=player_user).select_related("plan")
    plan_ids = [assignment.plan_id for assignment in assigned_plans]

    sessions = (
        TrainingSession.objects.filter(plan_id__in=plan_ids, session_date=selected_date)
        .select_related("plan")
        .order_by("plan__title", "start_time")
    )
    session_ids = [session.session_id for session in sessions]

    progress_map = {}
    if session_ids:
        progress_map = {
            progress.session_id: normalize_player_session_status(progress.status)
            for progress in PlayerSessionProgress.objects.filter(player=player_user, session_id__in=session_ids)
        }

    plans_out = {}
    total_sessions = 0
    completed_sessions = 0
    total_duration = 0

    for session in sessions:
        plan_key = str(session.plan.plan_id)
        plans_out.setdefault(plan_key, {"plan_id": plan_key, "title": session.plan.title, "sessions": []})

        status = progress_map.get(session.session_id, "not_started")
        duration = _duration_min(session.start_time, session.end_time)
        total_duration += duration
        total_sessions += 1
        if is_completed_player_session_status(status):
            completed_sessions += 1

        plans_out[plan_key]["sessions"].append(
            {
                "session_id": str(session.session_id),
                "title": session.title or "Session",
                "duration_min": duration,
                "status": status,
            }
        )

    final_plans = []
    for plan_payload in plans_out.values():
        sessions_list = plan_payload["sessions"]
        plan_payload["sessions_count"] = len(sessions_list)
        plan_payload["completed"] = len(sessions_list) > 0 and all(
            is_completed_player_session_status(session["status"]) for session in sessions_list
        )
        final_plans.append(plan_payload)

    final_plans.sort(key=lambda item: item["title"].lower())

    return {
        "date": str(selected_date),
        "header": {
            "month": selected_date.strftime("%B %Y"),
            "day": selected_date.day,
            "weekday": selected_date.strftime("%a"),
        },
        "summary": {
            "completed_sessions": completed_sessions,
            "total_sessions": total_sessions,
            "total_duration_min": total_duration,
        },
        "plans": final_plans,
    }

