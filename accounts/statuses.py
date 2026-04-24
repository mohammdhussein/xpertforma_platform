from xpertforma_platform.api_values import normalize_api_value


COACH_APPROVAL_PENDING = "PENDING"
COACH_APPROVAL_APPROVED = "APPROVED"
COACH_APPROVAL_REJECTED = "REJECTED"

VALID_COACH_APPROVAL_STATUSES = {
    COACH_APPROVAL_PENDING,
    COACH_APPROVAL_APPROVED,
    COACH_APPROVAL_REJECTED,
}

PLAYER_LOGIN_STATUS_FIRST_LOGIN = "FIRST_LOGIN"
PLAYER_LOGIN_STATUS_COMPLETE = "COMPLETE"

VALID_PLAYER_LOGIN_STATUSES = {
    PLAYER_LOGIN_STATUS_FIRST_LOGIN,
    PLAYER_LOGIN_STATUS_COMPLETE,
}

VALID_PLAYER_FOOT_VALUES = {"RIGHT", "LEFT", "BOTH"}
PLAYER_STATE_ACTIVE = "ACTIVE"
PLAYER_STATE_INJURED = "INJURED"

VALID_PLAYER_STATE_VALUES = {PLAYER_STATE_ACTIVE, PLAYER_STATE_INJURED}


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
    return normalize_api_value(value, default=default)


def normalize_player_foot_status(value, *, default=""):
    return normalize_api_value(value, default=default)


def parse_player_foot_api_value(value):
    normalized = normalize_api_value(value)
    return normalized if normalized in VALID_PLAYER_FOOT_VALUES else None


def normalize_player_state(value, *, default=""):
    return normalize_api_value(value, default=default)


def parse_player_state_api_value(value):
    normalized = normalize_api_value(value)
    return normalized if normalized in VALID_PLAYER_STATE_VALUES else None
