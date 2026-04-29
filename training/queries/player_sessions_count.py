from datetime import date as dt_date, timedelta

from django.db.models import Count
from django.utils.dateparse import parse_date

from accounts.exceptions import InvalidInputError
from training.models import (
    SessionAttendance,
    SessionLifecycle,
    TrainingPlanPlayer,
    TrainingSession,
)

DATE_FORMAT = "YYYY-MM-DD"
MAX_RANGE_DAYS = 31


def build_player_sessions_count_payload(player_user, *, start_date_str, end_date_str):
    start_date, end_date = _parse_range(start_date_str, end_date_str)

    plan_ids = list(
        TrainingPlanPlayer.objects
        .filter(player=player_user)
        .values_list("plan_id", flat=True)
    )

    totals_by_date: dict[dt_date, int] = {}
    completed_lifecycle_by_date: dict[dt_date, int] = {}
    in_progress_lifecycle_by_date: dict[dt_date, int] = {}
    attendance_by_date: dict[dt_date, int] = {}

    if plan_ids:
        total_rows = (
            TrainingSession.objects
            .filter(
                plan_id__in=plan_ids,
                session_date__range=(start_date, end_date),
            )
            .values("session_date")
            .annotate(total=Count("session_id"))
        )
        for row in total_rows:
            totals_by_date[row["session_date"]] = row["total"]

        lifecycle_rows = (
            SessionLifecycle.objects
            .filter(
                session__plan_id__in=plan_ids,
                session__session_date__range=(start_date, end_date),
            )
            .values("session__session_date", "status")
            .annotate(n=Count("session_id"))
        )
        for row in lifecycle_rows:
            day = row["session__session_date"]
            if row["status"] == SessionLifecycle.COMPLETED:
                completed_lifecycle_by_date[day] = (
                        completed_lifecycle_by_date.get(day, 0) + row["n"]
                )
            elif row["status"] == SessionLifecycle.IN_PROGRESS:
                in_progress_lifecycle_by_date[day] = (
                        in_progress_lifecycle_by_date.get(day, 0) + row["n"]
                )

        attendance_rows = (
            SessionAttendance.objects
            .filter(
                player=player_user,
                session__plan_id__in=plan_ids,
                session__session_date__range=(start_date, end_date),
                session__lifecycle__status=SessionLifecycle.COMPLETED,
            )
            .values("session__session_date")
            .annotate(n=Count("id"))
        )
        for row in attendance_rows:
            attendance_by_date[row["session__session_date"]] = row["n"]

    days = []
    span = (end_date - start_date).days
    for offset in range(span + 1):
        day = start_date + timedelta(days=offset)
        total = totals_by_date.get(day, 0)
        completed_lifecycle = completed_lifecycle_by_date.get(day, 0)
        in_progress = in_progress_lifecycle_by_date.get(day, 0)
        attendance = attendance_by_date.get(day, 0)

        completed = min(attendance, completed_lifecycle)
        missed = max(completed_lifecycle - completed, 0)
        not_started = max(total - completed_lifecycle - in_progress, 0)

        days.append({
            "date": day.isoformat(),
            "completed_count": completed,
            "missed_count": missed,
            "in_progress_count": in_progress,
            "not_started_count": not_started,
        })

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": days,
    }


def _parse_range(start_str, end_str) -> tuple[dt_date, dt_date]:
    if not start_str:
        raise InvalidInputError("start_date is required.", expected=[DATE_FORMAT])
    if not end_str:
        raise InvalidInputError("end_date is required.", expected=[DATE_FORMAT])

    start_date = parse_date(start_str.strip())
    if start_date is None:
        raise InvalidInputError("Invalid start_date format.", expected=[DATE_FORMAT])

    end_date = parse_date(end_str.strip())
    if end_date is None:
        raise InvalidInputError("Invalid end_date format.", expected=[DATE_FORMAT])

    if start_date > end_date:
        raise InvalidInputError("start_date must be less than or equal to end_date.")

    if (end_date - start_date).days + 1 > MAX_RANGE_DAYS:
        raise InvalidInputError(f"Date range must not exceed {MAX_RANGE_DAYS} days.")

    return start_date, end_date
