from rest_framework.exceptions import PermissionDenied

from accounts.exceptions import NotFoundError
from training.models import TrainingSession
from training.queries.training_session_details import serialize_training_session_details
from xpertforma_platform.api_values import normalize_api_value


def build_coach_session_details_payload(*, coach_user, plan_id, session_id):
    session = (
        TrainingSession.objects
        .select_related("plan", "lifecycle")
        .filter(plan_id=plan_id, session_id=session_id)
        .first()
    )
    if session is None:
        raise NotFoundError("Session not found in this plan.")
    if session.plan.creator_id != coach_user.id:
        raise PermissionDenied("Only the plan creator can view this session.")

    session_payload = serialize_training_session_details(session, title_fallback=session.plan.title)

    return {
        **session_payload,
        "plan": {
            "plan_id": session.plan.plan_id,
            "title": session.plan.title,
            "start_date": session.plan.start_date,
            "end_date": session.plan.end_date,
            "status": normalize_api_value(session.plan.status),
            "location": session.location,
            "intensity": session.intensity,
        },
    }
