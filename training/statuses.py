from xpertforma_platform.api_values import normalize_api_value


CANONICAL_COMPLETED_PLAYER_SESSION_STATUS = "completed"
COMPLETED_PLAYER_SESSION_STATUSES = {"complete", CANONICAL_COMPLETED_PLAYER_SESSION_STATUS}
VALID_PLAYER_SESSION_STATUSES = {
    "not_started",
    "in_progress",
    *COMPLETED_PLAYER_SESSION_STATUSES,
}
PLAYER_SESSION_STATUS_API_TO_DB = {
    "NOT_STARTED": "not_started",
    "IN_PROGRESS": "in_progress",
    "COMPLETED": CANONICAL_COMPLETED_PLAYER_SESSION_STATUS,
}
TRAINING_SESSION_TYPE_API_TO_DB = {
    "GROUP": "group",
    "TEAM": "team",
    "INDIVIDUAL": "individual",
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


def to_api_player_session_status(value, *, default="NOT_STARTED"):
    normalized = normalize_player_session_status(value, default="")
    if not normalized:
        return default
    return normalize_api_value(normalized, default=default)


def parse_player_session_status_api_value(value):
    return PLAYER_SESSION_STATUS_API_TO_DB.get(normalize_api_value(value))


def to_api_training_session_type(value, *, default=""):
    return normalize_api_value(value, default=default)


def parse_training_session_type_api_value(value):
    return TRAINING_SESSION_TYPE_API_TO_DB.get(normalize_api_value(value))


def to_api_training_plan_status(value, *, default=""):
    return normalize_api_value(value, default=default)

