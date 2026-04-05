from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ParseError, PermissionDenied

from training.models import PlayerSessionProgress, TrainingPlanPlayer, TrainingSession
from training.statuses import VALID_PLAYER_SESSION_STATUSES, normalize_player_session_status


def update_player_session_status(*, player_user, session_id, new_status):
    if new_status not in VALID_PLAYER_SESSION_STATUSES:
        raise ParseError(detail="Invalid status.")

    session = get_object_or_404(TrainingSession, session_id=session_id)
    if not TrainingPlanPlayer.objects.filter(plan=session.plan, player=player_user).exists():
        raise PermissionDenied(detail="Not allowed.")

    progress, _ = PlayerSessionProgress.objects.get_or_create(player=player_user, session=session)
    progress.status = normalize_player_session_status(new_status)
    progress.save(update_fields=["status", "updated_at"])

    return {"session_id": str(session.session_id), "status": normalize_player_session_status(progress.status)}

