from collections import defaultdict

from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.models import PlayerPerformanceSnapshot
from accounts.presenters.coach_player_profile import (
    build_overview_payload,
    build_plan_payloads,
    build_player_payload,
    build_recent_activity,
    build_stats_payload,
)
from accounts.presenters.coach_player_progress_metrics import (
    build_performance_metrics,
    calculate_attendance_summary,
    calculate_current_and_best_streaks,
    calculate_focus_area,
    calculate_progress_summary,
    calculate_progress_trend,
)
from accounts.queries.coach_players_list import get_coach_players_queryset
from accounts.services.coach_player_attention import build_coach_player_attention_items
from training.models import PlayerSessionProgress, TrainingPlanPlayer, TrainingSession
from training.statuses import normalize_player_session_status


def get_coach_player_profile_data(coach_user, player_id):
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

    total_sessions_count, progress_rate = calculate_progress_summary(sessions, progress_map)
    past_sessions, attendance_completed, attendance_total, attendance_rate = calculate_attendance_summary(
        sessions,
        progress_map,
        today=today,
    )
    progress_trend = calculate_progress_trend(sessions, progress_map, today=today)
    current_streak, best_streak = calculate_current_and_best_streaks(sessions, progress_map, today=today)

    snapshots = list(
        PlayerPerformanceSnapshot.objects.filter(player=player)
        .select_related("recorded_by")
        .order_by("-recorded_at", "-id")[:2]
    )
    latest_snapshot = snapshots[0] if snapshots else None
    previous_snapshot = snapshots[1] if len(snapshots) > 1 else None
    focus_area_name, focus_area_trend = calculate_focus_area(latest_snapshot, previous_snapshot)

    recent_activity = build_recent_activity(past_sessions, progress_map)
    latest_activity = recent_activity[0] if recent_activity else None
    needs_attention_items = build_coach_player_attention_items(
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

    plans_out, plans_done = build_plan_payloads(
        plans,
        sessions_by_plan,
        progress_map,
        progress_row_map,
        now=now,
    )
    performance_metrics = build_performance_metrics(latest_snapshot)

    return {
        "player": build_player_payload(
            player,
            player_profile,
            needs_attention=bool(needs_attention_items),
        ),
        "overview": build_overview_payload(
            needs_attention_items=needs_attention_items,
            latest_activity=latest_activity,
            attendance_completed=attendance_completed,
            attendance_rate=attendance_rate,
            attendance_total=attendance_total,
            progress_rate=progress_rate,
            progress_total=total_sessions_count,
            progress_trend=progress_trend,
            current_streak=current_streak,
            focus_area_name=focus_area_name,
            focus_area_trend=focus_area_trend,
            recent_activity=recent_activity,
        ),
        "stats": build_stats_payload(
            performance_metrics=performance_metrics,
            plans_done=plans_done,
            best_streak=best_streak,
        ),
        "plans": plans_out,
    }
