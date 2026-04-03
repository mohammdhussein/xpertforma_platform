from django.db import transaction
from django.contrib.auth.hashers import is_password_usable
from rest_framework import serializers
from rest_framework.exceptions import APIException
from accounts.models import User, Role, UserRole, PlayerProfile, Position
from accounts.serializers.position import (
    PositionSummarySerializer,
    build_position_payload,
)


class ConflictError(APIException):
    status_code = 409
    default_detail = "Conflict."
    default_code = "conflict"


class CoachCreatePlayerSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    position_id = serializers.PrimaryKeyRelatedField(
        source="position",
        queryset=Position.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        existing_user = User.objects.filter(email=email).first()
        if not existing_user:
            return email

        if hasattr(existing_user, "coach_profile") or hasattr(existing_user, "manager_profile"):
            raise serializers.ValidationError("A coach or manager account already uses this email.")
        return email

    @transaction.atomic
    def create(self, validated, coach_user):
        player_role, _ = Role.objects.get_or_create(role_name="Player")
        position = validated.get("position")
        email = validated["email"]

        user = User.objects.filter(email=email).first()
        created = False
        password_setup_required = False

        if user is None:
            user = User.objects.create_user(
                name=validated["name"],
                email=email,
                password=None,
            )
            created = True
            password_setup_required = True
        else:
            existing_profile = getattr(user, "player_profile", None)
            if existing_profile and existing_profile.coach_id == coach_user.id:
                raise ConflictError("A player with this email already exists for this coach.")

            if validated["name"] and user.name != validated["name"]:
                user.name = validated["name"]
                user.save(update_fields=["name"])
            password_setup_required = not is_password_usable(user.password)

        UserRole.objects.get_or_create(user=user, role=player_role)
        player_profile, _ = PlayerProfile.objects.update_or_create(
            user=user,
            defaults={
                "coach": coach_user,
                "position": position,
                "position_label": position.name if position else "",
                "login_status": "first_login" if password_setup_required else "complete",
            },
        )

        return (
            user,
            build_position_payload(player_profile.position, player_profile.position_label),
            created,
            password_setup_required,
        )


class PlayerCardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    position = PositionSummarySerializer()
    state = serializers.CharField()  # active / needs_review / injured


class PlayerListResponseSerializer(serializers.Serializer):
    players = PlayerCardSerializer(many=True)


class PlanProgressSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    title = serializers.CharField()
    started_at = serializers.DateField()
    status = serializers.CharField()  # active / completed
    overall_progress_percent = serializers.IntegerField()
    completed_sessions = serializers.IntegerField()
    remaining_sessions = serializers.IntegerField()


class PlayerHeaderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    age = serializers.IntegerField(allow_null=True)
    position = PositionSummarySerializer()


class PlayerTrainingProgressResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    age = serializers.IntegerField(allow_null=True)
    position = PositionSummarySerializer()
    plans = PlanProgressSerializer(many=True)
