from datetime import date as dt_date
from collections import defaultdict

from django.db.models import Count
from django.utils.dateparse import parse_date

from accounts.exceptions import InvalidInputError
from accounts.serializers.position import build_position_payload
from training.models import SessionLifecycle, TrainingPlan, TrainingPlanPlayer, TrainingSession
from training.serializers.training_plans import TrainingPlanDetailSerializer
from training.statuses import to_api_training_session_type
from xpertforma_platform.api_values import normalize_api_value

MAX_RANGE_DAYS = 31


def build_coach_training_plans_payload(coach_user, *, start_date_str=None, end_date_str=None):
    start_date, end_date = _parse_coach_plan_date_range(start_date_str=start_date_str, end_date_str=end_date_str)

    sessions = list(
        TrainingSession.objects
        .filter(
            plan__creator=coach_user,
            session_date__gte=start_date,
            session_date__lte=end_date,
        )
        .select_related("plan", "lifecycle")
        .order_by("session_date", "plan__title", "start_time")
    )

    sessions_by_date_and_plan = defaultdict(lambda: defaultdict(list))
    plan_titles = {}

    for session in sessions:
        plan_key = str(session.plan.plan_id)
        plan_titles[plan_key] = session.plan.title
        sessions_by_date_and_plan[session.session_date][plan_key].append(session)

    days = []
    for day in sorted(sessions_by_date_and_plan.keys()):
        plans_map = sessions_by_date_and_plan[day]
        plans_out = []
        for plan_key in sorted(plans_map.keys(), key=lambda key: plan_titles[key].lower()):
            plans_out.append(
                {
                    "plan_id": plan_key,
                    "title": plan_titles[plan_key],
                    "sessions": [
                        _serialize_coach_training_session(session)
                        for session in plans_map[plan_key]
                    ],
                }
            )
        days.append({"date": day.isoformat(), "plans": plans_out})

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": days,
    }


def get_coach_training_plans_queryset(coach_user):
    return (
        TrainingPlan.objects.filter(creator=coach_user)
        .annotate(
            total_sessions=Count("sessions", distinct=True),
            assigned_players=Count("trainingplanplayer", distinct=True),
        )
        .order_by("-start_date", "-end_date")
    )


def _parse_coach_plan_date_range(*, start_date_str, end_date_str):
    start_date = _parse_param_date(start_date_str, field="start_date")
    end_date = _parse_param_date(end_date_str, field="end_date")

    if start_date > end_date:
        raise InvalidInputError("start_date must be less than or equal to end_date.")

    span_days = (end_date - start_date).days + 1
    if span_days > MAX_RANGE_DAYS:
        raise InvalidInputError(f"Date range must not exceed {MAX_RANGE_DAYS} days.")

    return start_date, end_date


def _parse_param_date(value, *, field):
    if not value:
        return dt_date.today()
    parsed = parse_date(value)
    if not parsed:
        raise InvalidInputError(
            f"Invalid {field} format.",
            expected=["YYYY-MM-DD"],
        )
    return parsed


def _serialize_coach_training_session(session):
    lifecycle = getattr(session, "lifecycle", None)
    status = lifecycle.status if lifecycle else SessionLifecycle.NOT_STARTED

    return {
        "session_id": str(session.session_id),
        "title": session.title or "",
        "session_type": to_api_training_session_type(session.session_type),
        "session_date": session.session_date.isoformat(),
        "start_time": session.start_time.isoformat() if session.start_time else None,
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "intensity": normalize_api_value(session.intensity),
        "location": session.location,
        "squad_size": session.squad_size,
        "coach_note": session.coach_note,
        "status": status,
    }


def _build_time_range(start_time, end_time):
    if not start_time or not end_time:
        return ""
    return f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}"


def _day_label(value):
    return f"{value.strftime('%A')}, {value.strftime('%b')} {value.day}"


def build_training_plan_screen_payload(plan, request):
    assigned_rows = (
        TrainingPlanPlayer.objects.filter(plan=plan)
        .select_related("player", "player__player_profile", "player__player_profile__position")
        .order_by("player__first_name", "player__last_name", "player__email")
    )

    assigned_players = []
    for row in assigned_rows:
        player_profile = getattr(row.player, "player_profile", None)
        avatar_url = None
        if player_profile and getattr(player_profile, "avatar", None):
            avatar_url = request.build_absolute_uri(player_profile.avatar.url)

        assigned_players.append(
            {
                "id": row.player.id,
                "name": row.player.name,
                "position": build_position_payload(getattr(player_profile, "position", None)),
                "avatar_url": avatar_url,
            }
        )

    grouped_sessions = []
    current_date = None
    current_group = None
    for session in plan.sessions.all().order_by("session_date", "start_time"):
        if session.session_date != current_date:
            current_date = session.session_date
            current_group = {
                "session_date": session.session_date,
                "day_label": _day_label(session.session_date),
                "sessions": [],
            }
            grouped_sessions.append(current_group)

        current_group["sessions"].append(
            {
                "session_id": session.session_id,
                "title": session.title or plan.title,
                "session_type": to_api_training_session_type(session.session_type),
                "start_time": session.start_time,
                "end_time": session.end_time,
                "time_range": _build_time_range(session.start_time, session.end_time),
            }
        )

    return {
        **TrainingPlanDetailSerializer(plan).data,
        "assigned_players": assigned_players,
        "training_sessions": grouped_sessions,
    }

