from django.db import transaction
from django.contrib.auth.hashers import is_password_usable
from rest_framework import serializers
from accounts.exceptions import ConflictError
from accounts.models import User, Role, UserRole, PlayerProfile, Position, split_full_name
from accounts.serializers.position import (
    PositionSummarySerializer,
    build_position_payload,
)
from accounts.statuses import (
    PLAYER_LOGIN_STATUS_COMPLETE,
    PLAYER_LOGIN_STATUS_FIRST_LOGIN,
)
from xpertforma_platform.api_fields import UppercaseTokenField


class CoachCreatePlayerSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    position_id = serializers.PrimaryKeyRelatedField(
        source="position",
        queryset=Position.objects.all(),
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
        email = validated["email"]

        user = User.objects.filter(email=email).first()
        created = False
        password_setup_required = False
        existing_profile = None

        if user is None:
            first_name, last_name = split_full_name(validated["name"])
            user = User.objects.create_user(
                first_name=first_name,
                last_name=last_name,
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
                user.save(update_fields=["first_name", "last_name"])
            password_setup_required = not is_password_usable(user.password)

        UserRole.objects.get_or_create(user=user, role=player_role)
        profile_defaults = {
            "coach": coach_user,
            "login_status": (
                PLAYER_LOGIN_STATUS_FIRST_LOGIN
                if password_setup_required
                else PLAYER_LOGIN_STATUS_COMPLETE
            ),
        }
        if existing_profile is None or "position" in validated:
            profile_defaults["position"] = validated.get("position")

        player_profile, _ = PlayerProfile.objects.update_or_create(
            user=user,
            defaults=profile_defaults,
        )

        return (
            user,
            build_position_payload(player_profile.position),
            created,
            password_setup_required,
        )


class PlayerCardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    position = PositionSummarySerializer()
    state = UppercaseTokenField()
    needs_attention = serializers.BooleanField()
    expected_return_date = serializers.DateField(allow_null=True)
    avatar_url = serializers.CharField(allow_null=True)


class PlayerListResponseSerializer(serializers.Serializer):
    players = PlayerCardSerializer(many=True)


class CoachPlayerDetailPlayerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    dateOfBirth = serializers.DateField(allow_null=True)
    position = PositionSummarySerializer()
    avatar_url = serializers.CharField(allow_null=True)
    phone = serializers.CharField(allow_blank=True, allow_null=True)
    heightCm = serializers.FloatField(allow_null=True)
    weightKg = serializers.FloatField(allow_null=True)
    foot = UppercaseTokenField(allow_null=True)
    state = UppercaseTokenField()
    expectedReturnDate = serializers.DateField(allow_null=True)
    needsAttention = serializers.BooleanField()


class CoachPlayerNeedsAttentionSerializer(serializers.Serializer):
    id = serializers.CharField()
    message = serializers.CharField()
    severity = UppercaseTokenField()


class CoachPlayerProgressRateSerializer(serializers.Serializer):
    value = serializers.IntegerField()
    trend = UppercaseTokenField()


class CoachPlayerAttendanceSerializer(serializers.Serializer):
    completed = serializers.IntegerField()
    total = serializers.IntegerField()
    rate = serializers.IntegerField()


class CoachPlayerConsistencySerializer(serializers.Serializer):
    streakDays = serializers.IntegerField()


class CoachPlayerFocusAreaSerializer(serializers.Serializer):
    name = serializers.CharField(allow_null=True)
    trend = UppercaseTokenField()


class CoachPlayerKeyMetricsSerializer(serializers.Serializer):
    progressRate = CoachPlayerProgressRateSerializer()
    attendance = CoachPlayerAttendanceSerializer()
    consistency = CoachPlayerConsistencySerializer()
    focusArea = CoachPlayerFocusAreaSerializer()


class CoachPlayerRecentActivitySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    date = serializers.DateField()
    startTime = serializers.CharField(allow_blank=True)
    endTime = serializers.CharField(allow_blank=True)
    status = UppercaseTokenField()


class CoachPlayerOverviewSerializer(serializers.Serializer):
    needsAttention = CoachPlayerNeedsAttentionSerializer(many=True)
    keyMetrics = CoachPlayerKeyMetricsSerializer()
    coachInsights = serializers.ListField(child=serializers.CharField())
    recentActivity = CoachPlayerRecentActivitySerializer(many=True)


class CoachPlayerPerformanceMetricSerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.IntegerField(allow_null=True)


class CoachPlayerAchievementsSerializer(serializers.Serializer):
    plansDone = serializers.IntegerField()
    bestStreak = serializers.IntegerField()


class CoachPlayerStatsSerializer(serializers.Serializer):
    performanceMetrics = CoachPlayerPerformanceMetricSerializer(many=True)
    achievements = CoachPlayerAchievementsSerializer()


class CoachPlayerPlanSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    status = UppercaseTokenField()
    progress = serializers.IntegerField()
    completedSessions = serializers.IntegerField()
    remainingSessions = serializers.IntegerField()
    lastActivity = serializers.CharField(allow_null=True)


class PlayerTrainingProgressResponseSerializer(serializers.Serializer):
    player = CoachPlayerDetailPlayerSerializer()
    overview = CoachPlayerOverviewSerializer()
    stats = CoachPlayerStatsSerializer()
    plans = CoachPlayerPlanSerializer(many=True)
