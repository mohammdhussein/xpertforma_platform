from django.utils import timezone

from accounts.models import PlayerPerformanceSnapshot
from accounts.presenters.coach_player_progress_metrics import (
    calculate_attendance_summary,
    calculate_focus_area,
    is_final_player_session_status,
)
from accounts.services.coach_player_session_status import build_coach_player_session_status_maps
from accounts.statuses import PLAYER_STATE_INJURED
from training.models import TrainingPlanPlayer, TrainingSession
from training.statuses import is_completed_player_session_status


def calculate_attention_progress_summary(sessions, progress_map):
    reviewable_sessions = [
        session for session in sessions
        if is_final_player_session_status(progress_map.get(session.session_id))
    ]
    total = len(reviewable_sessions)
    if total == 0:
        return 0, 0

    completed = sum(
        1 for session in reviewable_sessions
        if is_completed_player_session_status(progress_map.get(session.session_id))
    )
    return total, int((completed / total) * 100)


def build_coach_player_attention_items(
    *,
    state,
    expected_return_date,
    latest_activity,
    attendance_rate,
    attendance_total,
    progress_rate,
    progress_total,
    focus_area_name,
    focus_area_trend,
):
    items = []

    if state == PLAYER_STATE_INJURED:
        message = "Player is currently marked as injured."
        if expected_return_date is not None:
            message = f"{message} Expected return date: {expected_return_date.isoformat()}."
        items.append(
            {
                "id": "player_injured",
                "message": message,
                "severity": "CRITICAL",
            }
        )

    if latest_activity and latest_activity["status"] == "MISSED":
        items.append(
            {
                "id": "missed_last_session",
                "message": "Missed last training session",
                "severity": "WARNING",
            }
        )

    if attendance_total > 0 and attendance_rate < 70:
        items.append(
            {
                "id": "low_attendance",
                "message": "Low attendance in scheduled training",
                "severity": "WARNING",
            }
        )

    if progress_total > 0 and progress_rate < 50:
        items.append(
            {
                "id": "low_progress",
                "message": "Low overall progress across assigned plans",
                "severity": "WARNING",
            }
        )

    if focus_area_name and focus_area_trend == "DOWN":
        items.append(
            {
                "id": "declining_focus_area",
                "message": f"Recent performance is declining in {focus_area_name.lower()}",
                "severity": "INFO",
            }
        )

    return items[:3]


def build_coach_player_attention_summary(player_profile, *, now=None):
    if player_profile.state == PLAYER_STATE_INJURED:
        items = build_coach_player_attention_items(
            state=player_profile.state,
            expected_return_date=player_profile.expected_return_date,
            latest_activity=None,
            attendance_rate=0,
            attendance_total=0,
            progress_rate=0,
            progress_total=0,
            focus_area_name=None,
            focus_area_trend="FLAT",
        )
        return {
            "needs_attention": bool(items),
            "items": items,
        }

    current_now = now or timezone.now()
    today = timezone.localdate(current_now)
    player = player_profile.user
    plan_ids = list(
        TrainingPlanPlayer.objects.filter(player=player).values_list("plan_id", flat=True)
    )
    sessions = list(
        TrainingSession.objects.filter(plan_id__in=plan_ids)
        .order_by("-session_date", "-start_time", "-session_id")
    )
    session_ids = [session.session_id for session in sessions]
    progress_map, _ = build_coach_player_session_status_maps(player, session_ids)

    total_sessions_count, progress_rate = calculate_attention_progress_summary(sessions, progress_map)
    past_sessions, _, attendance_total, attendance_rate = calculate_attendance_summary(
        sessions,
        progress_map,
        today=today,
    )

    snapshots = list(
        PlayerPerformanceSnapshot.objects.filter(player=player)
        .order_by("-recorded_at", "-id")[:2]
    )
    latest_snapshot = snapshots[0] if snapshots else None
    previous_snapshot = snapshots[1] if len(snapshots) > 1 else None
    focus_area_name, focus_area_trend = calculate_focus_area(latest_snapshot, previous_snapshot)

    latest_activity = _build_latest_activity(past_sessions, progress_map)
    items = build_coach_player_attention_items(
        state=player_profile.state,
        expected_return_date=player_profile.expected_return_date,
        latest_activity=latest_activity,
        attendance_rate=attendance_rate,
        attendance_total=attendance_total,
        progress_rate=progress_rate,
        progress_total=total_sessions_count,
        focus_area_name=focus_area_name,
        focus_area_trend=focus_area_trend,
    )

    return {
        "needs_attention": bool(items),
        "items": items,
        "evaluated_at": current_now,
    }


def _build_latest_activity(past_sessions, progress_map):
    for session in past_sessions:
        status = progress_map.get(session.session_id, "NOT_STARTED")
        return {
            "id": session.session_id,
            "status": "COMPLETED" if is_completed_player_session_status(status) else "MISSED",
        }
    return None
