COACH_APPROVAL_PENDING = "PENDING"
COACH_APPROVAL_APPROVED = "APPROVED"
COACH_APPROVAL_REJECTED = "REJECTED"


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

