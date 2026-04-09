COACH_APPROVAL_PENDING = "PENDING"
COACH_APPROVAL_APPROVED = "APPROVED"
COACH_APPROVAL_REJECTED = "REJECTED"

PLAYER_LOGIN_STATUS_FIRST_LOGIN = "FIRST_LOGIN"
PLAYER_LOGIN_STATUS_COMPLETE = "COMPLETE"


def normalize_coach_approval_status(value, *, default=""):
    if not value:
        return default
    return str(value).strip().upper()


def is_pending_coach_approval_status(value):
    return normalize_coach_approval_status(value) == COACH_APPROVAL_PENDING


def is_approved_coach_approval_status(value):
    return normalize_coach_approval_status(value) == COACH_APPROVAL_APPROVED


def is_rejected_coach_approval_status(value):
    return normalize_coach_approval_status(value) == COACH_APPROVAL_REJECTED


def normalize_player_login_status(value, *, default=""):
    if not value:
        return default

    normalized = str(value).strip().replace("-", "_").upper()
    if normalized == PLAYER_LOGIN_STATUS_FIRST_LOGIN:
        return PLAYER_LOGIN_STATUS_FIRST_LOGIN
    if normalized in {PLAYER_LOGIN_STATUS_COMPLETE, "COMPLETED"}:
        return PLAYER_LOGIN_STATUS_COMPLETE
    return normalized

