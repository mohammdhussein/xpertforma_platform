from collections import defaultdict
from datetime import datetime, timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.files import build_media_value_url
from accounts.models import PlayerPerformanceSnapshot, PlayerProfile
from accounts.serializers.position import build_position_payload
from training.models import PlayerSessionProgress, TrainingPlanPlayer, TrainingSession
from training.statuses import is_completed_player_session_status, normalize_player_session_status


def get_coach_players_queryset(coach_user):
    return PlayerProfile.objects.filter(coach=coach_user).select_related("user", "position")


def build_coach_players_list_payload(coach_user, *, query="", tab="all"):
    queryset = get_coach_players_queryset(coach_user)

    if query:
        queryset = queryset.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(position__name__icontains=query)
            | Q(position__code__icontains=query)
        )

    if tab != "all":
        queryset = queryset.filter(state=tab)

    players = []
    for profile in queryset.order_by("user__first_name", "user__last_name", "user__email"):
        players.append(
            {
                "id": profile.user.id,
                "name": profile.user.name,
                "position": build_position_payload(profile.position),
                "state": profile.state,
                "avatar_url": build_media_value_url(profile.avatar),
            }
        )

    return {"players": players}


def _duration_min(start_time, end_time):
    if not start_time or not end_time:
        return 0
    start_dt = datetime.combine(timezone.localdate(), start_time)
    end_dt = datetime.combine(timezone.localdate(), end_time)
    return max(int((end_dt - start_dt).total_seconds() // 60), 0)


def _build_time_range(start_time, end_time):
    if not start_time or not end_time:
        return ""
    return f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"


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


def _completion_rate(sessions, progress_map):
    total = len(sessions)
    if total == 0:
        return 0
    completed = sum(1 for session in sessions if is_completed_player_session_status(progress_map.get(session.session_id)))
    return int((completed / total) * 100)


def _trend_label(current_rate, previous_rate):
    if current_rate > previous_rate:
        return "up"
    if current_rate < previous_rate:
        return "down"
    return "flat"


def _scheduled_day_completion(sessions, progress_map, *, today):
    sessions_by_day = defaultdict(list)
    for session in sessions:
        if session.session_date <= today:
            sessions_by_day[session.session_date].append(session)

    day_completion = []
    for session_date in sorted(sessions_by_day):
        day_sessions = sessions_by_day[session_date]
        completed = all(
            is_completed_player_session_status(progress_map.get(session.session_id))
            for session in day_sessions
        )
        day_completion.append((session_date, completed))
    return day_completion


def _calculate_current_and_best_streaks(sessions, progress_map, *, today):
    day_completion = _scheduled_day_completion(sessions, progress_map, today=today)
    if not day_completion:
        return 0, 0

    best_streak = 0
    running_streak = 0
    for _, is_complete in day_completion:
        if is_complete:
            running_streak += 1
            best_streak = max(best_streak, running_streak)
        else:
            running_streak = 0

    current_streak = 0
    for _, is_complete in reversed(day_completion):
        if not is_complete:
            break
        current_streak += 1

    return current_streak, best_streak


def _normalize_focus_metric_key(value):
    if not value:
        return None
    normalized = str(value).strip().lower().replace(" ", "_")
    aliases = {
        "speed": "speed",
        "stamina": "stamina",
        "endurance": "stamina",
        "strength": "strength",
        "skills": "skills",
        "skill": "skills",
    }
    return aliases.get(normalized)


def _snapshot_focus_area(latest_snapshot, previous_snapshot):
    focus_display_names = {
        "speed": "Speed",
        "stamina": "Endurance",
        "strength": "Strength",
        "skills": "Skills",
    }

    metric_values = [
        ("speed", latest_snapshot.speed if latest_snapshot else None),
        ("stamina", latest_snapshot.stamina if latest_snapshot else None),
        ("strength", latest_snapshot.strength if latest_snapshot else None),
        ("skills", latest_snapshot.skills if latest_snapshot else None),
    ]

    focus_metric_key = None
    if latest_snapshot and latest_snapshot.focus_area_override:
        focus_metric_key = _normalize_focus_metric_key(latest_snapshot.focus_area_override)
        if focus_metric_key is None:
            return latest_snapshot.focus_area_override, "flat"

    if focus_metric_key is None:
        available_metrics = [(key, value) for key, value in metric_values if value is not None]
        if not available_metrics:
            return None, "flat"
        focus_metric_key = min(available_metrics, key=lambda item: (item[1], ["speed", "stamina", "strength", "skills"].index(item[0])))[0]

    current_value = getattr(latest_snapshot, focus_metric_key, None) if latest_snapshot else None
    previous_value = getattr(previous_snapshot, focus_metric_key, None) if previous_snapshot else None
    if current_value is None or previous_value is None:
        trend = "flat"
    else:
        trend = _trend_label(current_value, previous_value)

    return focus_display_names[focus_metric_key], trend


def _build_performance_metrics(latest_snapshot):
    return [
        {"name": "Speed", "value": getattr(latest_snapshot, "speed", None)},
        {"name": "Stamina", "value": getattr(latest_snapshot, "stamina", None)},
        {"name": "Strength", "value": getattr(latest_snapshot, "strength", None)},
        {"name": "Skills", "value": getattr(latest_snapshot, "skills", None)},
    ]


def _build_recent_activity(sessions, progress_map, *, limit=3):
    recent_activity = []
    for session in sessions:
        if len(recent_activity) >= limit:
            break
        status = progress_map.get(session.session_id, "not_started")
        recent_activity.append(
            {
                "id": session.session_id,
                "title": session.title or session.plan.title,
                "date": session.session_date,
                "timeRange": _build_time_range(session.start_time, session.end_time),
                "durationMinutes": _duration_min(session.start_time, session.end_time),
                "status": "completed" if is_completed_player_session_status(status) else "missed",
            }
        )
    return recent_activity


def _build_needs_attention(*, latest_activity, attendance_rate, attendance_total, progress_rate, progress_total, focus_area_name, focus_area_trend):
    items = []
    if latest_activity and latest_activity["status"] == "missed":
        items.append(
            {
                "id": "missed_last_session",
                "message": "Missed last training session",
                "severity": "warning",
            }
        )

    if attendance_total > 0 and attendance_rate < 70:
        items.append(
            {
                "id": "low_attendance",
                "message": "Low attendance in scheduled training",
                "severity": "warning",
            }
        )

    if progress_total > 0 and progress_rate < 50:
        items.append(
            {
                "id": "low_progress",
                "message": "Low overall progress across assigned plans",
                "severity": "warning",
            }
        )

    if focus_area_name and focus_area_trend == "down":
        items.append(
            {
                "id": "declining_focus_area",
                "message": f"Recent performance is declining in {focus_area_name.lower()}",
                "severity": "info",
            }
        )

    return items[:3]


def _build_coach_insight(*, attendance_rate, attendance_total, progress_rate, progress_total, focus_area_name, focus_area_trend, latest_activity):
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
        if focus_area_trend == "down":
            sentences.append(f"Recent performance in {focus_area_name} is declining.")

    if latest_activity and latest_activity["status"] == "missed":
        sentences.append("The most recent scheduled session was missed.")

    if not sentences:
        return "Not enough recent training data to generate insight."

    return " ".join(sentences)


def build_coach_player_training_progress_payload(coach_user, player_id):
    player_profile = get_object_or_404(
        get_coach_players_queryset(coach_user),
        user_id=player_id,
    )
    player = player_profile.user
    today = timezone.localdate()
    now = timezone.now()

    assignments = list(
        TrainingPlanPlayer.objects.filter(player=player).select_related("plan").order_by("-assigned_at")
    )
    plans = [assignment.plan for assignment in assignments]
    plan_ids = [plan.plan_id for plan in plans]

    sessions = list(
        TrainingSession.objects.filter(plan_id__in=plan_ids)
        .select_related("plan")
        .order_by("-session_date", "-start_time", "-session_id")
    )
    session_ids = [session.session_id for session in sessions]
    progress_rows = list(
        PlayerSessionProgress.objects.filter(player=player, session_id__in=session_ids).order_by("-updated_at")
    )
    progress_map = {
        progress.session_id: normalize_player_session_status(progress.status)
        for progress in progress_rows
    }
    progress_row_map = {progress.session_id: progress for progress in progress_rows}

    sessions_by_plan = defaultdict(list)
    for session in sessions:
        sessions_by_plan[session.plan_id].append(session)

    past_sessions = [session for session in sessions if session.session_date <= today]
    total_sessions_count = len(sessions)
    completed_sessions_count = sum(
        1 for session in sessions if is_completed_player_session_status(progress_map.get(session.session_id))
    )
    progress_rate = int((completed_sessions_count / total_sessions_count) * 100) if total_sessions_count else 0

    attendance_total = len(past_sessions)
    attendance_completed = sum(
        1 for session in past_sessions if is_completed_player_session_status(progress_map.get(session.session_id))
    )
    attendance_rate = int((attendance_completed / attendance_total) * 100) if attendance_total else 0

    current_window_start = today - timedelta(days=6)
    previous_window_start = current_window_start - timedelta(days=7)
    previous_window_end = current_window_start - timedelta(days=1)
    current_window_sessions = [session for session in sessions if current_window_start <= session.session_date <= today]
    previous_window_sessions = [
        session for session in sessions if previous_window_start <= session.session_date <= previous_window_end
    ]
    progress_trend = _trend_label(
        _completion_rate(current_window_sessions, progress_map),
        _completion_rate(previous_window_sessions, progress_map),
    )

    current_streak, best_streak = _calculate_current_and_best_streaks(sessions, progress_map, today=today)

    snapshots = list(
        PlayerPerformanceSnapshot.objects.filter(player=player)
        .select_related("recorded_by")
        .order_by("-recorded_at", "-id")[:2]
    )
    latest_snapshot = snapshots[0] if snapshots else None
    previous_snapshot = snapshots[1] if len(snapshots) > 1 else None
    focus_area_name, focus_area_trend = _snapshot_focus_area(latest_snapshot, previous_snapshot)

    recent_activity = _build_recent_activity(past_sessions, progress_map)
    latest_activity = recent_activity[0] if recent_activity else None

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
                progress_row_map[session.session_id].updated_at
                for session in plan_sessions
                if session.session_id in progress_row_map
            ),
            default=None,
        )
        latest_session_date = max((session.session_date for session in plan_sessions), default=plan.start_date)

        plans_out.append(
            {
                "id": plan.plan_id,
                "title": plan.title,
                "status": "completed" if percent >= 100 else "active",
                "progress": percent,
                "completedSessions": completed,
                "remainingSessions": remaining,
                "lastActivity": _format_relative_time(latest_progress_dt, now=now),
                "_sort_session_date": latest_session_date,
            }
        )

    plans_out.sort(
        key=lambda item: (
            0 if item["status"] == "active" else 1,
            -item["_sort_session_date"].toordinal(),
            item["title"].lower(),
        )
    )
    for item in plans_out:
        item.pop("_sort_session_date", None)

    return {
        "player": {
            "id": player.id,
            "name": player.name,
            "dateOfBirth": player.date_of_birth,
            "position": player_profile.position.name if player_profile.position else None,
            "phone": player.phone,
            "heightCm": player_profile.height_cm,
            "weightKg": player_profile.weight_kg,
            "foot": player_profile.get_foot_display() if player_profile.foot else None,
        },
        "overview": {
            "needsAttention": _build_needs_attention(
                latest_activity=latest_activity,
                attendance_rate=attendance_rate,
                attendance_total=attendance_total,
                progress_rate=progress_rate,
                progress_total=total_sessions_count,
                focus_area_name=focus_area_name,
                focus_area_trend=focus_area_trend,
            ),
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
            "coachInsight": _build_coach_insight(
                attendance_rate=attendance_rate,
                attendance_total=attendance_total,
                progress_rate=progress_rate,
                progress_total=total_sessions_count,
                focus_area_name=focus_area_name,
                focus_area_trend=focus_area_trend,
                latest_activity=latest_activity,
            ),
            "recentActivity": recent_activity,
        },
        "stats": {
            "performanceMetrics": _build_performance_metrics(latest_snapshot),
            "achievements": {
                "plansDone": plans_done,
                "bestStreak": best_streak,
            },
        },
        "plans": plans_out,
    }

