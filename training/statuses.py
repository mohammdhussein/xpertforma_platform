CANONICAL_COMPLETED_PLAYER_SESSION_STATUS = "completed"
COMPLETED_PLAYER_SESSION_STATUSES = {"complete", CANONICAL_COMPLETED_PLAYER_SESSION_STATUS}
VALID_PLAYER_SESSION_STATUSES = {
    "not_started",
    "in_progress",
    *COMPLETED_PLAYER_SESSION_STATUSES,
}


def normalize_player_session_status(value, *, default="not_started"):
    if not value:
        return default
    status = str(value).strip()
    if status in COMPLETED_PLAYER_SESSION_STATUSES:
        return CANONICAL_COMPLETED_PLAYER_SESSION_STATUS
    return status


def is_completed_player_session_status(value):
    return normalize_player_session_status(value, default="") == CANONICAL_COMPLETED_PLAYER_SESSION_STATUS

