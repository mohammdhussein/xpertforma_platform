from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ParseError, PermissionDenied

from training.models import PlayerSessionProgress, TrainingPlanPlayer, TrainingSession
from training.statuses import (
    normalize_player_session_status,
    parse_player_session_status_api_value,
    to_api_player_session_status,
)
from xpertforma_platform.api_values import normalize_api_value


def update_player_session_status(*, player_user, session_id, new_status):
    if new_status != normalize_api_value(new_status):
        raise ParseError(detail="Invalid status. Use uppercase values.")

    parsed_status = parse_player_session_status_api_value(new_status)
    if parsed_status is None:
        raise ParseError(detail="Invalid status.")

    session = get_object_or_404(TrainingSession, session_id=session_id)
    if not TrainingPlanPlayer.objects.filter(plan=session.plan, player=player_user).exists():
        raise PermissionDenied(detail="Not allowed.")

    progress, _ = PlayerSessionProgress.objects.get_or_create(player=player_user, session=session)
    progress.status = normalize_player_session_status(parsed_status)
    progress.save(update_fields=["status", "updated_at"])

    return {"session_id": str(session.session_id), "status": to_api_player_session_status(progress.status)}

