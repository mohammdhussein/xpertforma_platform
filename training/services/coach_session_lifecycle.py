from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from accounts.exceptions import ConflictError, InvalidInputError, NotFoundError
from training.models import (
    SessionAttendance,
    SessionLifecycle,
    TrainingPlanPlayer,
    TrainingSession,
)
from training.queries.training_session_details import serialize_training_session_details


def _get_session_or_404(plan_id, session_id) -> TrainingSession:
    session = (
        TrainingSession.objects
        .select_related("plan")
        .filter(session_id=session_id, plan_id=plan_id)
        .first()
    )
    if session is None:
        raise NotFoundError("Session not found in this plan.")
    return session


def _ensure_plan_owner(coach_user, session: TrainingSession) -> None:
    if session.plan.creator_id != coach_user.id:
        raise PermissionDenied("Only the plan creator can manage this session.")


def _assigned_player_ids(plan_id) -> set:
    return set(
        TrainingPlanPlayer.objects
        .filter(plan_id=plan_id)
        .values_list("player_id", flat=True)
    )


def _build_response(session: TrainingSession, lifecycle: SessionLifecycle) -> dict:
    assigned_ids = _assigned_player_ids(session.plan_id)
    present_ids = set(
        SessionAttendance.objects
        .filter(session=session)
        .values_list("player_id", flat=True)
    )
    missed_ids = assigned_ids - present_ids
    return {
        **serialize_training_session_details(session, title_fallback=session.plan.title, lifecycle=lifecycle),
        "present_player_ids": sorted(str(pid) for pid in present_ids),
        "missed_player_ids": sorted(str(pid) for pid in missed_ids),
    }


@transaction.atomic
def start_session(*, coach_user, plan_id, session_id, present_player_ids):
    session = _get_session_or_404(plan_id, session_id)
    _ensure_plan_owner(coach_user, session)

    lifecycle = SessionLifecycle.objects.select_for_update().filter(session=session).first()
    if lifecycle is not None and lifecycle.status != SessionLifecycle.NOT_STARTED:
        raise ConflictError("Session has already been started.")

    requested_ids = {str(pid) for pid in present_player_ids}
    if requested_ids:
        assigned_ids = {str(pid) for pid in _assigned_player_ids(plan_id)}
        invalid = requested_ids - assigned_ids
        if invalid:
            raise InvalidInputError(
                "presentPlayerIds contains players not assigned to this plan.",
                expected=sorted(assigned_ids),
            )

    now = timezone.now()
    lifecycle, _ = SessionLifecycle.objects.update_or_create(
        session=session,
        defaults={
            "status": SessionLifecycle.IN_PROGRESS,
            "started_at": now,
            "started_by": coach_user,
            "ended_at": None,
            "ended_by": None,
        },
    )

    for player_id in requested_ids:
        SessionAttendance.objects.update_or_create(
            session=session,
            player_id=player_id,
            defaults={
                "status": SessionAttendance.PRESENT,
                "marked_by": coach_user,
            },
        )

    return _build_response(session, lifecycle)


@transaction.atomic
def end_session(*, coach_user, plan_id, session_id):
    session = _get_session_or_404(plan_id, session_id)
    _ensure_plan_owner(coach_user, session)

    lifecycle = SessionLifecycle.objects.select_for_update().filter(session=session).first()
    if lifecycle is None or lifecycle.status != SessionLifecycle.IN_PROGRESS:
        raise ConflictError("Session must be in progress to be ended.")

    lifecycle.status = SessionLifecycle.COMPLETED
    lifecycle.ended_at = timezone.now()
    lifecycle.ended_by = coach_user
    lifecycle.save(update_fields=["status", "ended_at", "ended_by"])

    return _build_response(session, lifecycle)
