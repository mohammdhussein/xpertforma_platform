from collections import defaultdict
from datetime import date as dt_date

from django.utils.dateparse import parse_date

from accounts.exceptions import InvalidInputError
from training.models import (
    SessionAttendance,
    SessionLifecycle,
    TrainingPlanPlayer,
    TrainingSession,
)
from training.queries.training_session_details import (
    get_session_lifecycle,
    serialize_training_session_details,
)
from training.statuses import (
    derive_session_player_status_api_value,
)

MAX_RANGE_DAYS = 31


def build_player_training_payload(player_user, *, start_date_str, end_date_str):
    start_date = _parse_param_date(start_date_str, field="start_date")
    end_date = _parse_param_date(end_date_str, field="end_date")

    if start_date > end_date:
        raise InvalidInputError("start_date must be less than or equal to end_date.")

    span_days = (end_date - start_date).days + 1
    if span_days > MAX_RANGE_DAYS:
        raise InvalidInputError(f"Date range must not exceed {MAX_RANGE_DAYS} days.")

    plan_ids = list(
        TrainingPlanPlayer.objects
        .filter(player=player_user)
        .values_list("plan_id", flat=True)
    )

    sessions = []
    if plan_ids:
        sessions = list(
            TrainingSession.objects
            .filter(
                plan_id__in=plan_ids,
                session_date__gte=start_date,
                session_date__lte=end_date,
            )
            .select_related("plan", "lifecycle")
            .order_by("session_date", "plan__title", "start_time")
        )

    attendance_set: set = set()
    if sessions:
        session_ids = [s.session_id for s in sessions]
        attendance_set = set(
            SessionAttendance.objects
            .filter(player=player_user, session_id__in=session_ids)
            .values_list("session_id", flat=True)
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
        for plan_key in sorted(plans_map.keys(), key=lambda k: plan_titles[k].lower()):
            plans_out.append({
                "plan_id": plan_key,
                "title": plan_titles[plan_key],
                "sessions": [
                    _serialize_session(s, attendance_set)
                    for s in plans_map[plan_key]
                ],
            })
        days.append({"date": day.isoformat(), "plans": plans_out})

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": days,
    }


def _parse_param_date(value: str | None, *, field: str) -> dt_date:
    if not value:
        return dt_date.today()
    parsed = parse_date(value)
    if not parsed:
        raise InvalidInputError(
            f"Invalid {field} format.",
            expected=["YYYY-MM-DD"],
        )
    return parsed


def _serialize_session(
        session: TrainingSession,
        attendance_set: set,
) -> dict:
    lifecycle = get_session_lifecycle(session)
    lifecycle_status = lifecycle.status if lifecycle else SessionLifecycle.NOT_STARTED
    has_attendance = session.session_id in attendance_set
    player_status = derive_session_player_status_api_value(
        lifecycle_status, has_attendance=has_attendance,
    )

    return serialize_training_session_details(
        session,
        lifecycle=lifecycle,
        status=player_status,
    )
