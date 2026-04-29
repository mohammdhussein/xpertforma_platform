from django.core.exceptions import ObjectDoesNotExist

from training.models import SessionLifecycle, TrainingSession
from training.statuses import to_api_training_session_type
from xpertforma_platform.api_values import normalize_api_value


def get_session_lifecycle(session: TrainingSession):
    try:
        return session.lifecycle
    except ObjectDoesNotExist:
        return None


def serialize_lifecycle(lifecycle) -> dict:
    status = lifecycle.status if lifecycle else SessionLifecycle.NOT_STARTED
    return {
        "status": normalize_api_value(status),
        "started_at": lifecycle.started_at.isoformat() if lifecycle and lifecycle.started_at else None,
        "ended_at": lifecycle.ended_at.isoformat() if lifecycle and lifecycle.ended_at else None,
    }


def serialize_training_session_details(
        session: TrainingSession,
        *,
        title_fallback="",
        lifecycle=None,
        status=None,
) -> dict:
    lifecycle = lifecycle if lifecycle is not None else get_session_lifecycle(session)
    lifecycle_payload = serialize_lifecycle(lifecycle)
    status_value = normalize_api_value(status or lifecycle_payload["status"])

    return {
        "session_id": str(session.session_id),
        "title": session.title or title_fallback or "",
        "session_type": to_api_training_session_type(session.session_type),
        "session_date": session.session_date.isoformat(),
        "start_time": session.start_time.isoformat() if session.start_time else None,
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "intensity": normalize_api_value(session.intensity),
        "location": session.location,
        "notes": session.notes,
        "status": status_value,
        "lifecycle": lifecycle_payload,
    }
