from collections import defaultdict
from datetime import timedelta

from training.statuses import is_completed_player_session_status


def calculate_completion_rate(sessions, progress_map):
    total = len(sessions)
    if total == 0:
        return 0
    completed = sum(1 for session in sessions if is_completed_player_session_status(progress_map.get(session.session_id)))
    return int((completed / total) * 100)


def calculate_trend_label(current_rate, previous_rate):
    if current_rate > previous_rate:
        return "UP"
    if current_rate < previous_rate:
        return "DOWN"
    return "FLAT"


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


def calculate_current_and_best_streaks(sessions, progress_map, *, today):
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


def calculate_focus_area(latest_snapshot, previous_snapshot):
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
            return latest_snapshot.focus_area_override, "FLAT"

    if focus_metric_key is None:
        available_metrics = [(key, value) for key, value in metric_values if value is not None]
        if not available_metrics:
            return None, "FLAT"
        focus_metric_key = min(
            available_metrics,
            key=lambda item: (item[1], ["speed", "stamina", "strength", "skills"].index(item[0])),
        )[0]

    current_value = getattr(latest_snapshot, focus_metric_key, None) if latest_snapshot else None
    previous_value = getattr(previous_snapshot, focus_metric_key, None) if previous_snapshot else None
    if current_value is None or previous_value is None:
        trend = "FLAT"
    else:
        trend = calculate_trend_label(current_value, previous_value)

    return focus_display_names[focus_metric_key], trend


def build_performance_metrics(latest_snapshot):
    return [
        {"name": "Speed", "value": getattr(latest_snapshot, "speed", None)},
        {"name": "Stamina", "value": getattr(latest_snapshot, "stamina", None)},
        {"name": "Strength", "value": getattr(latest_snapshot, "strength", None)},
        {"name": "Skills", "value": getattr(latest_snapshot, "skills", None)},
    ]


def calculate_progress_summary(sessions, progress_map):
    total_sessions_count = len(sessions)
    completed_sessions_count = sum(
        1 for session in sessions if is_completed_player_session_status(progress_map.get(session.session_id))
    )
    progress_rate = int((completed_sessions_count / total_sessions_count) * 100) if total_sessions_count else 0
    return total_sessions_count, progress_rate


def calculate_attendance_summary(sessions, progress_map, *, today):
    past_sessions = [session for session in sessions if session.session_date <= today]
    attendance_total = len(past_sessions)
    attendance_completed = sum(
        1 for session in past_sessions if is_completed_player_session_status(progress_map.get(session.session_id))
    )
    attendance_rate = int((attendance_completed / attendance_total) * 100) if attendance_total else 0
    return past_sessions, attendance_completed, attendance_total, attendance_rate


def calculate_progress_trend(sessions, progress_map, *, today):
    current_window_start = today - timedelta(days=6)
    previous_window_start = current_window_start - timedelta(days=7)
    previous_window_end = current_window_start - timedelta(days=1)
    current_window_sessions = [session for session in sessions if current_window_start <= session.session_date <= today]
    previous_window_sessions = [
        session for session in sessions if previous_window_start <= session.session_date <= previous_window_end
    ]
    return calculate_trend_label(
        calculate_completion_rate(current_window_sessions, progress_map),
        calculate_completion_rate(previous_window_sessions, progress_map),
    )
