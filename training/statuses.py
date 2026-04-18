from django.db import models

from xpertforma_platform.api_values import normalize_api_value


# ── Checkin ──────────────────────────────────────────────────────────────────

class SleepQuality(models.TextChoices):
    POOR  = "poor",  "Poor"
    FAIR  = "fair",  "Fair"
    GOOD  = "good",  "Good"
    GREAT = "great", "Great"


SLEEP_QUALITY_SCORE = {
    SleepQuality.POOR:  0.0,
    SleepQuality.FAIR:  0.5,
    SleepQuality.GOOD:  0.8,
    SleepQuality.GREAT: 1.0,
}

VALID_SORE_ZONES = [
    "head_neck", "shoulders", "upper_back", "lower_back",
    "hip_groin", "left_quad", "right_quad", "hamstring",
    "knee", "calf", "ankle_foot",
]


# ── Training session ─────────────────────────────────────────────────────────

class Intensity(models.TextChoices):
    LOW    = "low",    "Low"
    MEDIUM = "medium", "Medium"
    HIGH   = "high",   "High"


# ── AI insights ──────────────────────────────────────────────────────────────

class InsightTag(models.TextChoices):
    LOAD      = "load",      "Load"
    INTENSITY = "intensity", "Intensity"
    RECOVERY  = "recovery",  "Recovery"


# ── Player session status ─────────────────────────────────────────────────────

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
    "COMPLETED":   CANONICAL_COMPLETED_PLAYER_SESSION_STATUS,
}
TRAINING_SESSION_TYPE_API_TO_DB = {
    "GROUP":      "group",
    "TEAM":       "team",
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


def derive_session_player_status_api_value(lifecycle_status, *, has_attendance):
    if lifecycle_status == "completed":
        return "COMPLETED" if has_attendance else "MISSED"
    if lifecycle_status == "in_progress":
        return "IN_PROGRESS"
    return "NOT_STARTED"


def to_api_training_session_type(value, *, default=""):
    return normalize_api_value(value, default=default)


def parse_training_session_type_api_value(value):
    return TRAINING_SESSION_TYPE_API_TO_DB.get(normalize_api_value(value))


def to_api_training_plan_status(value, *, default=""):
    return normalize_api_value(value, default=default)
