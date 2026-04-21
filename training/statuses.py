from django.db import models

from xpertforma_platform.api_values import normalize_api_value


# ── Checkin ──────────────────────────────────────────────────────────────────

class SleepQuality(models.TextChoices):
    POOR  = "POOR",  "Poor"
    FAIR  = "FAIR",  "Fair"
    GOOD  = "GOOD",  "Good"
    GREAT = "GREAT", "Great"


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
    LOW    = "LOW",    "Low"
    MEDIUM = "MEDIUM", "Medium"
    HIGH   = "HIGH",   "High"


VALID_TRAINING_SESSION_TYPES = {"GROUP", "TEAM", "INDIVIDUAL"}


# ── AI insights ──────────────────────────────────────────────────────────────

class InsightTag(models.TextChoices):
    LOAD      = "LOAD",      "Load"
    INTENSITY = "INTENSITY", "Intensity"
    RECOVERY  = "RECOVERY",  "Recovery"


# ── Player session status ─────────────────────────────────────────────────────

PLAYER_SESSION_STATUS_NOT_STARTED = "NOT_STARTED"
PLAYER_SESSION_STATUS_IN_PROGRESS = "IN_PROGRESS"
PLAYER_SESSION_STATUS_COMPLETED   = "COMPLETED"

VALID_PLAYER_SESSION_STATUSES = {
    PLAYER_SESSION_STATUS_NOT_STARTED,
    PLAYER_SESSION_STATUS_IN_PROGRESS,
    PLAYER_SESSION_STATUS_COMPLETED,
}


def normalize_player_session_status(value, *, default=PLAYER_SESSION_STATUS_NOT_STARTED):
    if not value:
        return default
    return normalize_api_value(value, default=default)


def is_completed_player_session_status(value):
    return normalize_player_session_status(value, default="") == PLAYER_SESSION_STATUS_COMPLETED


def to_api_player_session_status(value, *, default=PLAYER_SESSION_STATUS_NOT_STARTED):
    return normalize_player_session_status(value, default=default)


def parse_player_session_status_api_value(value):
    normalized = normalize_api_value(value)
    return normalized if normalized in VALID_PLAYER_SESSION_STATUSES else None


def derive_session_player_status_api_value(lifecycle_status, *, has_attendance):
    if lifecycle_status == PLAYER_SESSION_STATUS_COMPLETED:
        return "COMPLETED" if has_attendance else "MISSED"
    if lifecycle_status == PLAYER_SESSION_STATUS_IN_PROGRESS:
        return PLAYER_SESSION_STATUS_IN_PROGRESS
    return PLAYER_SESSION_STATUS_NOT_STARTED


def to_api_training_session_type(value, *, default=""):
    return normalize_api_value(value, default=default)


def parse_training_session_type_api_value(value):
    normalized = normalize_api_value(value)
    return normalized if normalized in VALID_TRAINING_SESSION_TYPES else None


def to_api_training_plan_status(value, *, default=""):
    return normalize_api_value(value, default=default)
