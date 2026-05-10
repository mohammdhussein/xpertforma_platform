from collections import defaultdict
from datetime import timedelta

from django.utils.dateparse import parse_date

from accounts.exceptions import InvalidInputError
from training.queries.player_performance import (
    get_checkins_by_date,
    get_completed_attendance_session_ids,
    get_player_sessions,
)
from training.statuses import Intensity

DATE_FORMAT = "YYYY-MM-DD"
EFFORT_SOURCE = "INTENSITY_WEIGHTED_SESSION_COMPLETION"
RECOVERY_SOURCE = "PLAYER_CHECKINS"
MAX_RANGE_DAYS = 31
INTENSITY_WEIGHTS = {
    Intensity.LOW: 1,
    Intensity.MEDIUM: 2,
    Intensity.HIGH: 3,
}


def build_player_performance_payload(player_user, *, start_date_str, end_date_str):
    start_date, end_date = _parse_range(start_date_str, end_date_str)
    sessions = get_player_sessions(player_user, start_date=start_date, end_date=end_date)
    session_ids = [session.session_id for session in sessions]
    completed_session_ids = get_completed_attendance_session_ids(player_user, session_ids)
    checkins_by_date = get_checkins_by_date(player_user, start_date=start_date, end_date=end_date)

    planned_by_date, completed_by_date, planned_effort_by_date, completed_effort_by_date = _build_session_counts(
        sessions,
        completed_session_ids,
    )
    streak_days_by_date = _build_streak_days_by_date(
        start_date=start_date,
        end_date=end_date,
        planned_by_date=planned_by_date,
        completed_by_date=completed_by_date,
    )
    days = []
    for day in _date_range(start_date, end_date):
        planned = planned_by_date.get(day, 0)
        completed = completed_by_date.get(day, 0)
        sessions_percentage = _percentage(completed, planned)
        effort_percentage = _percentage(
            completed_effort_by_date.get(day, 0),
            planned_effort_by_date.get(day, 0),
        )
        consistency_percentage = _percentage(completed, planned)
        recovery_percentage = _recovery_percentage(checkins_by_date.get(day))
        score = _score(
            planned=planned,
            effort_percentage=effort_percentage,
            recovery_percentage=recovery_percentage,
            consistency_percentage=consistency_percentage,
        )

        days.append({
            "date": day.isoformat(),
            "score": score,
            "sessions": {
                "completed": completed,
                "planned": planned,
                "percentage": sessions_percentage,
            },
            "effort": {
                "percentage": effort_percentage,
                "source": EFFORT_SOURCE,
            },
            "recovery": {
                "percentage": recovery_percentage,
                "source": RECOVERY_SOURCE,
            },
            "consistency": {
                "percentage": consistency_percentage,
                "streak_days": streak_days_by_date.get(day, 0),
            },
        })

    return {"days": days}


def _parse_range(start_str, end_str):
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


def _date_range(start_date, end_date):
    for offset in range((end_date - start_date).days + 1):
        yield start_date + timedelta(days=offset)


def _build_session_counts(sessions, completed_session_ids):
    planned_by_date = defaultdict(int)
    completed_by_date = defaultdict(int)
    planned_effort_by_date = defaultdict(int)
    completed_effort_by_date = defaultdict(int)

    for session in sessions:
        intensity_weight = _intensity_weight(session.intensity)
        planned_by_date[session.session_date] += 1
        planned_effort_by_date[session.session_date] += intensity_weight
        if session.session_id in completed_session_ids:
            completed_by_date[session.session_date] += 1
            completed_effort_by_date[session.session_date] += intensity_weight

    return planned_by_date, completed_by_date, planned_effort_by_date, completed_effort_by_date


def _intensity_weight(intensity):
    return INTENSITY_WEIGHTS.get(intensity, INTENSITY_WEIGHTS[Intensity.MEDIUM])


def _percentage(numerator, denominator):
    if not denominator:
        return 0
    return _clamp(round(numerator / denominator * 100))


def _clamp(value):
    return max(0, min(100, int(value)))


def _recovery_percentage(checkin):
    if checkin is None:
        return 0
    return _clamp(checkin.readiness_score)


def _score(*, planned, effort_percentage, recovery_percentage, consistency_percentage):
    if planned > 0:
        raw_score = (
            effort_percentage * 0.5
            + recovery_percentage * 0.35
            + consistency_percentage * 0.15
        )
    else:
        raw_score = recovery_percentage * 0.7 + consistency_percentage * 0.3
    return _clamp(round(raw_score))


def _build_streak_days_by_date(*, start_date, end_date, planned_by_date, completed_by_date):
    streak_days_by_date = {}
    running_streak = 0
    for day in _date_range(start_date, end_date):
        planned = planned_by_date.get(day, 0)
        completed = completed_by_date.get(day, 0)
        if planned > 0 and completed == planned:
            running_streak += 1
        elif planned > 0:
            running_streak = 0
        streak_days_by_date[day] = running_streak
    return streak_days_by_date
