from django.db import transaction
from django.utils.dateparse import parse_date
from rest_framework import serializers

from training.models import TrainingPlanPlayer, TrainingSession
from training.serializers.training_plans import (
    AssignPlayersSerializer,
    SessionCreateSerializer,
    TrainingPlanCreateSerializer,
)
from training.statuses import to_api_training_session_type


def _normalize_sessions_payload(*, raw_sessions, start_date, end_date):
    if not isinstance(raw_sessions, list):
        raise serializers.ValidationError({"detail": "sessions must be a list."})

    normalized_sessions = []
    for session_payload in raw_sessions:
        day_str = session_payload.get("date")
        if not day_str:
            raise serializers.ValidationError({"detail": "Each session must include a 'date' field."})

        session_date = parse_date(day_str)
        if not session_date:
            raise serializers.ValidationError(
                {"detail": f"Invalid session date format: {day_str}. Use YYYY-MM-DD."}
            )
        if session_date < start_date or session_date > end_date:
            raise serializers.ValidationError(
                {"detail": f"Session date {day_str} is outside plan date range."}
            )

        serializer = SessionCreateSerializer(
            data={
                "title": session_payload.get("title", ""),
                "session_type": session_payload.get(
                    "session_type",
                    to_api_training_session_type(TrainingSession.SESSION_TYPE_GROUP),
                ),
                "start_time": session_payload.get("start_time"),
                "end_time": session_payload.get("end_time"),
                "notes": session_payload.get("notes", ""),
            }
        )
        serializer.is_valid(raise_exception=True)
        validated_session = serializer.validated_data
        normalized_sessions.append(
            {
                "session_date": session_date,
                "title": validated_session.get("title", ""),
                "session_type": validated_session.get("session_type", TrainingSession.SESSION_TYPE_GROUP),
                "start_time": validated_session.get("start_time"),
                "end_time": validated_session.get("end_time"),
                "notes": validated_session.get("notes", ""),
            }
        )

    return normalized_sessions


def _validate_assignee_players(coach_user, raw_assignee_players):
    if not isinstance(raw_assignee_players, list):
        raise serializers.ValidationError({"detail": "assignee_players must be a list."})

    player_ids_raw = []
    for item in raw_assignee_players:
        if not isinstance(item, dict) or "id" not in item:
            raise serializers.ValidationError(
                {"detail": "Each assignee_players item must be an object with an 'id' field."}
            )
        player_ids_raw.append(item["id"])

    if not player_ids_raw:
        raise serializers.ValidationError({"assignee_players": ["At least one player must be selected."]})

    serializer = AssignPlayersSerializer(data={"player_ids": player_ids_raw})
    serializer.is_valid(raise_exception=True)
    validated_player_ids = serializer.validated_data["player_ids"]

    allowed_id_set = set(
        coach_user.coached_players.filter(user_id__in=validated_player_ids).values_list("user_id", flat=True)
    )
    invalid_ids = set(validated_player_ids) - allowed_id_set
    if invalid_ids:
        raise serializers.ValidationError(
            {
                "assignee_players": ["You can only assign players currently linked to the signed-in coach."],
                "invalid_player_ids": [str(player_id) for player_id in sorted(invalid_ids)],
            }
        )

    return [player_id for player_id in validated_player_ids if player_id in allowed_id_set]


@transaction.atomic
def create_coach_training_plan(*, coach_user, payload):
    plan_serializer = TrainingPlanCreateSerializer(
        data={
            "title": payload.get("title"),
            "start_date": payload.get("start_date"),
            "end_date": payload.get("end_date"),
        }
    )
    plan_serializer.is_valid(raise_exception=True)
    validated_plan = plan_serializer.validated_data

    normalized_sessions = _normalize_sessions_payload(
        raw_sessions=payload.get("sessions") or [],
        start_date=validated_plan["start_date"],
        end_date=validated_plan["end_date"],
    )
    allowed_player_ids = _validate_assignee_players(
        coach_user,
        payload.get("assignee_players") or [],
    )

    plan = plan_serializer.save(creator=coach_user, status="DRAFT")
    created_sessions = [
        TrainingSession.objects.create(plan=plan, **session_payload)
        for session_payload in normalized_sessions
    ]

    if allowed_player_ids:
        TrainingPlanPlayer.objects.bulk_create(
            [
                TrainingPlanPlayer(plan=plan, player_id=player_id, assigned_by=coach_user)
                for player_id in allowed_player_ids
            ]
        )

    return {
        "message": "Training plan (with sessions and players) created successfully.",
        "plan": plan,
        "sessions": created_sessions,
        "assigned_player_ids": allowed_player_ids,
    }
