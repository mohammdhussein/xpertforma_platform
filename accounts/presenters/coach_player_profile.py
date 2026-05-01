from django.utils import timezone

from accounts.files import build_media_value_url
from accounts.serializers.position import build_position_payload
from accounts.statuses import normalize_player_foot_status, normalize_player_state
from training.statuses import is_completed_player_session_status


def _format_time_value(value):
    if not value:
        return ""
    return value.strftime("%H:%M")


def _format_relative_time(value, *, now=None):
    if value is None:
        return None

    current = now or timezone.now()
    delta = current - value
    total_seconds = max(int(delta.total_seconds()), 0)

    if total_seconds < 60:
        return "just now"

    total_minutes = total_seconds // 60
    if total_minutes < 60:
        unit = "minute" if total_minutes == 1 else "minutes"
        return f"{total_minutes} {unit} ago"

    total_hours = total_minutes // 60
    if total_hours < 24:
        unit = "hour" if total_hours == 1 else "hours"
        return f"{total_hours} {unit} ago"

    total_days = total_hours // 24
    unit = "day" if total_days == 1 else "days"
    return f"{total_days} {unit} ago"


def build_recent_activity(sessions, progress_map, *, limit=3):
    recent_activity = []
    for session in sessions:
        if len(recent_activity) >= limit:
            break
        status = progress_map.get(session.session_id, "NOT_STARTED")
        recent_activity.append(
            {
                "id": session.session_id,
                "title": session.title or session.plan.title,
                "date": session.session_date,
                "startTime": _format_time_value(session.start_time),
                "endTime": _format_time_value(session.end_time),
                "status": "COMPLETED" if is_completed_player_session_status(status) else "MISSED",
            }
        )
    return recent_activity


def build_coach_insights(
    *,
    attendance_rate,
    attendance_total,
    progress_rate,
    progress_total,
    focus_area_name,
    focus_area_trend,
    latest_activity,
):
    sentences = []

    if attendance_total > 0:
        if attendance_rate >= 80:
            sentences.append("Attendance is high and the player is consistent with scheduled training.")
        elif attendance_rate >= 60:
            sentences.append("Attendance is moderate and consistency can improve.")
        else:
            sentences.append("Attendance is low and needs attention.")

    if progress_total > 0:
        if progress_rate >= 75:
            sentences.append("The player is showing strong progress across assigned plans.")
        elif progress_rate >= 50:
            sentences.append("The player is making steady progress across assigned plans.")
        else:
            sentences.append("The player needs support improving progress across assigned plans.")

    if focus_area_name:
        sentences.append(f"Current focus area is {focus_area_name}.")
        if focus_area_trend == "DOWN":
            sentences.append(f"Recent performance in {focus_area_name} is declining.")

    if latest_activity and latest_activity["status"] == "MISSED":
        sentences.append("The most recent scheduled session was missed.")

    if not sentences:
        return ["Not enough recent training data to generate insight."]

    return sentences


def build_plan_payloads(plans, sessions_by_plan, progress_map, activity_dt_map, *, now):
    plans_out = []
    plans_done = 0

    for plan in plans:
        plan_sessions = sessions_by_plan.get(plan.plan_id, [])
        total = len(plan_sessions)
        completed = sum(
            1 for session in plan_sessions if is_completed_player_session_status(progress_map.get(session.session_id))
        )
        remaining = max(total - completed, 0)
        percent = int((completed / total) * 100) if total > 0 else 0
        if total > 0 and completed == total:
            plans_done += 1

        latest_progress_dt = max(
            (
                activity_dt_map[session.session_id]
                for session in plan_sessions
                if activity_dt_map.get(session.session_id) is not None
            ),
            default=None,
        )
        latest_session_date = max((session.session_date for session in plan_sessions), default=plan.start_date)

        plans_out.append(
            {
                "id": plan.plan_id,
                "title": plan.title,
                "status": "COMPLETED" if percent >= 100 else "ACTIVE",
                "progress": percent,
                "completedSessions": completed,
                "remainingSessions": remaining,
                "lastActivity": _format_relative_time(latest_progress_dt, now=now),
                "_sort_session_date": latest_session_date,
            }
        )

    plans_out.sort(
        key=lambda item: (
            0 if item["status"] == "ACTIVE" else 1,
            -item["_sort_session_date"].toordinal(),
            item["title"].lower(),
        )
    )
    for item in plans_out:
        item.pop("_sort_session_date", None)

    return plans_out, plans_done


def build_player_payload(player, player_profile, *, needs_attention):
    return {
        "id": player.id,
        "name": player.name,
        "dateOfBirth": player.date_of_birth,
        "position": build_position_payload(player_profile.position),
        "avatar_url": build_media_value_url(player_profile.avatar),
        "phone": player.phone,
        "heightCm": player_profile.height_cm,
        "weightKg": player_profile.weight_kg,
        "foot": normalize_player_foot_status(player_profile.foot, default=None),
        "state": normalize_player_state(player_profile.state),
        "expectedReturnDate": player_profile.expected_return_date,
        "needsAttention": needs_attention,
    }


def build_overview_payload(
    *,
    needs_attention_items,
    latest_activity,
    attendance_completed,
    attendance_rate,
    attendance_total,
    progress_rate,
    progress_total,
    progress_trend,
    current_streak,
    focus_area_name,
    focus_area_trend,
    recent_activity,
):
    return {
        "needsAttention": needs_attention_items,
        "keyMetrics": {
            "progressRate": {
                "value": progress_rate,
                "trend": progress_trend,
            },
            "attendance": {
                "completed": attendance_completed,
                "total": attendance_total,
                "rate": attendance_rate,
            },
            "consistency": {
                "streakDays": current_streak,
            },
            "focusArea": {
                "name": focus_area_name,
                "trend": focus_area_trend,
            },
        },
        "coachInsights": build_coach_insights(
            attendance_rate=attendance_rate,
            attendance_total=attendance_total,
            progress_rate=progress_rate,
            progress_total=progress_total,
            focus_area_name=focus_area_name,
            focus_area_trend=focus_area_trend,
            latest_activity=latest_activity,
        ),
        "recentActivity": recent_activity,
    }


def build_stats_payload(*, performance_metrics, plans_done, best_streak):
    return {
        "performanceMetrics": performance_metrics,
        "achievements": {
            "plansDone": plans_done,
            "bestStreak": best_streak,
        },
    }

