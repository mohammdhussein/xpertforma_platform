from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPlayer
from training.models import TrainingPlanPlayer, TrainingSession, PlayerSessionProgress
from training.statuses import (
    is_completed_player_session_status,
    normalize_player_session_status,
    to_api_player_session_status,
)
from accounts.serializers.player_dashboard import PlayerDashboardSerializer
from accounts.utils import duration_minutes


def _build_weekly_completion_points(user, plan_ids, week_start, week_end):
    """
    Build per-day completion percentage values for the chart.
    value = completed_sessions / total_sessions * 100
    Also returns aggregate completed/total counts and total minutes of completed sessions.
    """
    sessions = (
        TrainingSession.objects
        .filter(plan_id__in=plan_ids, session_date__gte=week_start, session_date__lt=week_end)
        .only("session_date", "start_time", "end_time", "session_id")
    )

    session_ids = [s.session_id for s in sessions]
    progress_map = {}
    if session_ids:
        progress_map = {
            p.session_id: p.status
            for p in PlayerSessionProgress.objects.filter(player=user, session_id__in=session_ids)
        }

    per_day_total = {}
    per_day_completed = {}
    completed_minutes = 0

    for s in sessions:
        day = s.session_date
        per_day_total[day] = per_day_total.get(day, 0) + 1
        status = progress_map.get(s.session_id)
        is_completed = is_completed_player_session_status(status)
        if is_completed:
            per_day_completed[day] = per_day_completed.get(day, 0) + 1
            completed_minutes += duration_minutes(s.start_time, s.end_time)

    labels = ["M", "T", "W", "T", "F", "S", "S"]
    points = []

    total_completed = 0
    total_sessions = 0

    for offset, label in enumerate(labels):
        day = week_start + timedelta(days=offset)
        day_total = per_day_total.get(day, 0)
        day_completed = per_day_completed.get(day, 0)

        total_sessions += day_total
        total_completed += day_completed

        if day_total > 0:
            value = int((day_completed / day_total) * 100)
        else:
            value = 0

        points.append({"date": day, "day_label": label, "value": value})

    return points, total_completed, total_sessions, completed_minutes


def _aggregate_week_completion(user, plan_ids, start_date, end_date):
    """
    Aggregate completed vs total sessions for a given week window.
    Used to compute percent change vs last week.
    """
    sessions = (
        TrainingSession.objects
        .filter(plan_id__in=plan_ids, session_date__gte=start_date, session_date__lt=end_date)
        .only("session_date", "session_id")
    )
    session_ids = [s.session_id for s in sessions]
    if not session_ids:
        return 0, 0

    progress_map = {
        p.session_id: p.status
        for p in PlayerSessionProgress.objects.filter(player=user, session_id__in=session_ids)
    }

    completed = 0
    for s in sessions:
        status = progress_map.get(s.session_id)
        if is_completed_player_session_status(status):
            completed += 1

    total = len(session_ids)
    return completed, total


def _build_nutrition_summary(total_weekly_minutes):
    # Simple estimate based on total training minutes; replace with real nutrition data later.
    burned = max(total_weekly_minutes * 8, 0)  # ~8 kcal per active minute
    calories_goal = 2400
    calories_used = min(burned, calories_goal)
    calories_remaining = max(calories_goal - calories_used, 0)

    protein_goal = 150
    carb_goal = 300
    fat_goal = 80

    # Distribute used calories into macros
    protein_current = min(int(calories_used * 0.3 / 4), protein_goal)
    carbs_current = min(int(calories_used * 0.5 / 4), carb_goal)
    fats_current = min(int(calories_used * 0.2 / 9), fat_goal)

    return {
        "calories_remaining": calories_remaining,
        "calories_goal": calories_goal,
        "protein": {"current_g": protein_current, "target_g": protein_goal},
        "carbs": {"current_g": carbs_current, "target_g": carb_goal},
        "fats": {"current_g": fats_current, "target_g": fat_goal},
    }


class PlayerDashboardAPIView(APIView):
    """
    Screen: Player Dashboard (session, nutrition summary, weekly overview)
    """

    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        user = request.user
        today = timezone.localdate()

        assignments = (
            TrainingPlanPlayer.objects
            .filter(player=user)
            .select_related("plan")
        )
        plan_ids = [a.plan_id for a in assignments]

        week_start = today - timedelta(days=today.weekday())  # Monday
        week_end = week_start + timedelta(days=7)

        # Next upcoming session for this player (today or later)
        upcoming_qs = (
            TrainingSession.objects
            .filter(plan_id__in=plan_ids, session_date__gte=today)
            .select_related("plan")
            .order_by("session_date", "start_time")
        )
        next_session = upcoming_qs.first()

        session_data = None
        if next_session:
            progress = PlayerSessionProgress.objects.filter(
                player=user, session=next_session
            ).first()
            raw_status = progress.status if progress else "not_started"
            status_label = to_api_player_session_status(raw_status)

            session_data = {
                "session_id": next_session.session_id,
                "plan_id": next_session.plan_id,
                "title": next_session.title or next_session.plan.title,
                "session_date": next_session.session_date,
                "start_time": next_session.start_time,
                "end_time": next_session.end_time,
                "duration_min": duration_minutes(next_session.start_time, next_session.end_time),
                "status": status_label,
            }

        weekly_points, completed_week, total_week, completed_minutes_week = _build_weekly_completion_points(
            user, plan_ids, week_start, week_end
        )

        completed_last_week, total_last_week = _aggregate_week_completion(
            user,
            plan_ids,
            week_start - timedelta(days=7),
            week_start,
        )

        this_week_rate = int((completed_week / total_week) * 100) if total_week > 0 else 0
        last_week_rate = int((completed_last_week / total_last_week) * 100) if total_last_week > 0 else 0

        percent_change = this_week_rate - last_week_rate
        is_up = percent_change >= 0

        today_label = today.strftime("%a")[0]
        today_value = 0
        for point in weekly_points:
            if point["date"] == today:
                today_label = point["day_label"]
                today_value = point["value"]
                break

        # Average only across days that actually have sessions to better match UI expectations.
        non_zero_days = [p["value"] for p in weekly_points if p["value"] > 0]
        if non_zero_days:
            average_value = int(sum(non_zero_days) / len(non_zero_days))
        else:
            average_value = 0

        weekly_overview = {
            "percent_change_vs_last_week": percent_change,
            "is_up": is_up,
            "series": [
                {"day_label": p["day_label"], "value": p["value"]}
                for p in weekly_points
            ],
            "today_label": today_label,
            "today_value": today_value,
            "average_value": average_value,
        }

        # Use minutes from completed sessions this week as proxy for calories burned.
        nutrition = _build_nutrition_summary(completed_minutes_week)

        payload = {
            "session": session_data,
            "nutrition": nutrition,
            "weekly_overview": weekly_overview,
        }

        return Response(PlayerDashboardSerializer(payload).data)
