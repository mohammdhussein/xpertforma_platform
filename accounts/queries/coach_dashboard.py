from collections import defaultdict
from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import PlayerProfile
from accounts.services.coach_alerts import build_coach_alerts
from training.models import SessionAttendance, TrainingPlanPlayer, TrainingSession
from training.statuses import to_api_training_session_type

UPCOMING_SESSIONS_LIMIT = 3


def _start_of_week_sunday(d):
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _attendance_rate(plan_ids, player_ids, week_start, week_end):
    sessions_qs = TrainingSession.objects.filter(
        plan_id__in=plan_ids,
        session_date__gte=week_start,
        session_date__lt=week_end,
    )
    session_ids = list(sessions_qs.values_list("session_id", flat=True))
    if not session_ids:
        return None, 0

    plan_counts = dict(
        TrainingPlanPlayer.objects.filter(plan_id__in=plan_ids, player_id__in=player_ids)
        .values("plan_id")
        .annotate(c=Count("player_id", distinct=True))
        .values_list("plan_id", "c")
    )
    expected = sum(plan_counts.get(s.plan_id, 0) for s in sessions_qs)
    if expected == 0:
        return None, 0

    attended = SessionAttendance.objects.filter(
        session_id__in=session_ids,
        player_id__in=player_ids,
        status__in=["PRESENT", "LATE"],
    ).count()
    return round(attended / expected * 100), expected


def build_coach_dashboard_payload(coach_user, *, now) -> dict:
    today = now.date()
    current_time = now.time()

    week_start = _start_of_week_sunday(today)
    last_week_start = week_start - timedelta(days=7)

    player_profiles = PlayerProfile.objects.filter(coach=coach_user).select_related("user", "position")
    player_ids = list(player_profiles.values_list("user_id", flat=True))
    plan_ids = list(
        TrainingPlanPlayer.objects.filter(player_id__in=player_ids)
        .values_list("plan_id", flat=True)
        .distinct()
    )

    # --- overview_stats.total_players ---
    total_all = player_profiles.count()
    active_count = player_profiles.filter(state="ACTIVE").count()
    month_start = today.replace(day=1)
    delta_value = PlayerProfile.objects.filter(
        coach=coach_user, state="ACTIVE", user__created_at__date__gte=month_start
    ).count()

    # --- overview_stats.sessions_today ---
    sessions_today_qs = TrainingSession.objects.filter(
        plan_id__in=plan_ids, session_date=today
    ).select_related("lifecycle")

    today_count = sessions_today_qs.count()
    completed_today = sum(
        1 for s in sessions_today_qs
        if hasattr(s, "lifecycle") and s.lifecycle.ended_at is not None
    )
    next_session = (
        sessions_today_qs
        .filter(start_time__isnull=False, start_time__gte=current_time)
        .order_by("start_time")
        .first()
    )
    next_start_time = next_session.start_time.strftime("%H:%M") if next_session else None
    today_pct = round(completed_today / today_count * 100) if today_count > 0 else 0

    # --- overview_stats.attendance_week ---
    curr_pct, _ = _attendance_rate(plan_ids, player_ids, week_start, week_start + timedelta(days=7))
    last_pct, _ = _attendance_rate(plan_ids, player_ids, last_week_start, week_start)
    if curr_pct is not None and last_pct is not None:
        delta_pct = curr_pct - last_pct
    else:
        delta_pct = None

    # --- overview_stats.attention + alerts ---
    all_alerts, total_alerts = build_coach_alerts(coach_user, limit=None, now=now)
    critical_count = sum(1 for a in all_alerts if a["severity"] == "CRITICAL")
    attn_pct = round(critical_count / total_all * 100) if total_all > 0 else 0
    top_alerts = all_alerts[:3]

    # --- upcoming_sessions (48h window) ---
    deadline = now + timedelta(hours=48)
    deadline_date = deadline.date()
    deadline_time = deadline.time()

    upcoming_qs = list(
        TrainingSession.objects
        .filter(plan_id__in=plan_ids, start_time__isnull=False)
        .filter(Q(session_date__gt=today) | Q(session_date=today, start_time__gte=current_time))
        .filter(Q(session_date__lt=deadline_date) | Q(session_date=deadline_date, start_time__lte=deadline_time))
        .select_related("plan")
        .order_by("session_date", "start_time")[:UPCOMING_SESSIONS_LIMIT]
    )

    upcoming_plan_ids = [s.plan_id for s in upcoming_qs]

    players_count_map = dict(
        TrainingPlanPlayer.objects
        .filter(plan_id__in=upcoming_plan_ids, player_id__in=player_ids)
        .values("plan_id")
        .annotate(c=Count("player_id", distinct=True))
        .values_list("plan_id", "c")
    )

    assigned_players_map: dict = defaultdict(list)
    for row in (
        TrainingPlanPlayer.objects
        .filter(plan_id__in=upcoming_plan_ids, player_id__in=player_ids)
        .values("plan_id", "player_id")
    ):
        assigned_players_map[row["plan_id"]].append({"id": row["player_id"]})

    upcoming_out = []
    for s in upcoming_qs:
        upcoming_out.append({
            "session_id": s.session_id,
            "plan_id": s.plan_id,
            "title": s.title or s.plan.title,
            "session_date": s.session_date,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "location": s.location,
            "assigned_players": assigned_players_map.get(s.plan_id, []),
            "session_type": to_api_training_session_type(s.session_type),
            "players_count": players_count_map.get(s.plan_id, 0),
        })

    return {
        "overview_stats": {
            "total_players": {
                "value": active_count,
                "delta_value": delta_value,
            },
            "sessions_today": {
                "value": today_count,
                "completed_count": completed_today,
                "next_start_time": next_start_time,
                "progress_percent": today_pct,
            },
            "attendance_week": {
                "value_percent": curr_pct,
                "delta_percent": delta_pct,
            },
            "attention": {
                "value": critical_count,
                "progress_percent": attn_pct,
            },
        },
        "alerts": top_alerts,
        "alerts_total": total_alerts,
        "upcoming_sessions": upcoming_out,
    }
