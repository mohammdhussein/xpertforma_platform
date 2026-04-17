from xpertforma_platform.api_values import normalize_api_value


COACH_APPROVAL_PENDING = "PENDING"
COACH_APPROVAL_APPROVED = "APPROVED"
COACH_APPROVAL_REJECTED = "REJECTED"

PLAYER_LOGIN_STATUS_FIRST_LOGIN = "FIRST_LOGIN"
PLAYER_LOGIN_STATUS_COMPLETE = "COMPLETE"
PLAYER_FOOT_API_TO_DB = {
    "RIGHT": "right",
    "LEFT": "left",
    "BOTH": "both",
}
PLAYER_STATE_API_TO_DB = {
    "ACTIVE": "active",
    "INJURED": "injured",
    "NEEDS_REVIEW": "needs_review",
}


def normalize_coach_approval_status(value, *, default=""):
    return normalize_api_value(value, default=default)


def is_pending_coach_approval_status(value):
    return normalize_coach_approval_status(value) == COACH_APPROVAL_PENDING


def is_approved_coach_approval_status(value):
    return normalize_coach_approval_status(value) == COACH_APPROVAL_APPROVED


def is_rejected_coach_approval_status(value):
    return normalize_coach_approval_status(value) == COACH_APPROVAL_REJECTED


def normalize_player_login_status(value, *, default=""):
    if not value:
        return default

    normalized = normalize_api_value(value, default=default)
    if normalized == PLAYER_LOGIN_STATUS_FIRST_LOGIN:
        return PLAYER_LOGIN_STATUS_FIRST_LOGIN
    if normalized in {PLAYER_LOGIN_STATUS_COMPLETE, "COMPLETED"}:
        return PLAYER_LOGIN_STATUS_COMPLETE
    return normalized


def normalize_player_foot_status(value, *, default=""):
    return normalize_api_value(value, default=default)


def parse_player_foot_api_value(value):
    return PLAYER_FOOT_API_TO_DB.get(normalize_api_value(value))


def normalize_player_state(value, *, default=""):
    return normalize_api_value(value, default=default)


def parse_player_state_api_value(value):
    return PLAYER_STATE_API_TO_DB.get(normalize_api_value(value))

