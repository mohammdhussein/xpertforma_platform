from training.models import (
    PlayerSessionProgress,
    SessionAttendance,
    SessionLifecycle,
)
from training.statuses import (
    PLAYER_SESSION_STATUS_COMPLETED,
    PLAYER_SESSION_STATUS_IN_PROGRESS,
    PLAYER_SESSION_STATUS_NOT_STARTED,
    derive_session_player_status_api_value,
    normalize_player_session_status,
)


def build_coach_player_session_status_maps(player, session_ids):
    progress_rows = list(
        PlayerSessionProgress.objects
        .filter(player=player, session_id__in=session_ids)
        .order_by("-updated_at")
    )
    status_map = {
        progress.session_id: normalize_player_session_status(progress.status)
        for progress in progress_rows
    }
    activity_dt_map = {
        progress.session_id: progress.updated_at
        for progress in progress_rows
    }

    lifecycle_rows = list(SessionLifecycle.objects.filter(session_id__in=session_ids))
    if not lifecycle_rows:
        return status_map, activity_dt_map

    attendance_rows = list(
        SessionAttendance.objects
        .filter(player=player, session_id__in=session_ids)
        .values("session_id", "marked_at")
    )
    attended_session_ids = {row["session_id"] for row in attendance_rows}
    attendance_marked_at_map = {
        row["session_id"]: row["marked_at"]
        for row in attendance_rows
    }

    for lifecycle in lifecycle_rows:
        session_id = lifecycle.session_id
        if lifecycle.status == SessionLifecycle.COMPLETED:
            status_map[session_id] = derive_session_player_status_api_value(
                PLAYER_SESSION_STATUS_COMPLETED,
                has_attendance=session_id in attended_session_ids,
            )
            activity_dt_map[session_id] = attendance_marked_at_map.get(session_id) or lifecycle.ended_at
        elif lifecycle.status == SessionLifecycle.IN_PROGRESS:
            status_map[session_id] = PLAYER_SESSION_STATUS_IN_PROGRESS
            activity_dt_map[session_id] = lifecycle.started_at
        else:
            status_map[session_id] = PLAYER_SESSION_STATUS_NOT_STARTED

    return status_map, activity_dt_map
