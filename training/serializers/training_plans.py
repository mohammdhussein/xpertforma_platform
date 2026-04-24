from rest_framework import serializers

from accounts.exceptions import InvalidInputError
from accounts.serializers.position import PositionSummarySerializer
from training.models import TrainingPlan, TrainingSession
from training.statuses import VALID_TRAINING_SESSION_TYPES, parse_training_session_type_api_value
from xpertforma_platform.api_fields import UppercaseTokenField
from xpertforma_platform.api_values import normalize_api_value


class TrainingPlanCreateSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date must be after or equal to start date."})
        return attrs

    class Meta:
        model = TrainingPlan
        fields = ["plan_id", "title", "start_date", "end_date"]
        read_only_fields = ["plan_id"]


class TrainingPlanDetailSerializer(serializers.ModelSerializer):
    total_sessions = serializers.IntegerField(read_only=True)
    assigned_players_count = serializers.IntegerField(source="assigned_players", read_only=True)
    status = UppercaseTokenField()

    class Meta:
        model = TrainingPlan
        fields = ["plan_id", "title", "start_date", "end_date", "status", "total_sessions", "assigned_players_count"]


class CoachTrainingPlanRangeSessionSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    title = serializers.CharField()
    session_type = UppercaseTokenField()
    session_date = serializers.DateField()
    start_time = serializers.TimeField(allow_null=True)
    end_time = serializers.TimeField(allow_null=True)
    intensity = UppercaseTokenField(allow_blank=True, allow_null=True)
    location = serializers.CharField(allow_blank=True)
    squad_size = serializers.IntegerField(allow_null=True)
    coach_note = serializers.CharField(allow_blank=True)
    status = UppercaseTokenField()


class CoachTrainingPlanRangePlanSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    title = serializers.CharField()
    sessions = CoachTrainingPlanRangeSessionSerializer(many=True)


class CoachTrainingPlanRangeDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    plans = CoachTrainingPlanRangePlanSerializer(many=True)


class CoachTrainingPlanRangeResponseSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    days = CoachTrainingPlanRangeDaySerializer(many=True)


class SessionCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120, required=False, allow_blank=True)
    session_type = serializers.CharField(required=False, default="GROUP")
    start_time = serializers.TimeField(required=False, allow_null=True)
    end_time = serializers.TimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_session_type(self, value):
        expected_session_types = sorted(VALID_TRAINING_SESSION_TYPES)

        if value != normalize_api_value(value):
            raise InvalidInputError(
                "Invalid session_type. Use uppercase values.",
                expected=expected_session_types,
            )

        parsed = parse_training_session_type_api_value(value)
        if parsed is None:
            raise InvalidInputError(
                "Invalid session_type.",
                expected=expected_session_types,
            )

        return parsed

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")

        if (start_time is None) != (end_time is None):
            raise serializers.ValidationError({"detail": "start_time and end_time must both be provided together."})
        if start_time is not None and end_time is not None and end_time <= start_time:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        return attrs


class TrainingSessionSerializer(serializers.ModelSerializer):
    session_type = UppercaseTokenField()

    class Meta:
        model = TrainingSession
        fields = ["session_id", "plan", "session_date", "title", "session_type", "start_time", "end_time", "notes"]
        read_only_fields = ["session_id", "plan", "session_date"]


class PlanAssignedPlayerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    position = PositionSummarySerializer()
    avatar_url = serializers.CharField(allow_null=True)


class PlanSessionItemSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    title = serializers.CharField()
    session_type = UppercaseTokenField()
    start_time = serializers.TimeField(allow_null=True)
    end_time = serializers.TimeField(allow_null=True)
    time_range = serializers.CharField()


class PlanSessionGroupSerializer(serializers.Serializer):
    session_date = serializers.DateField()
    day_label = serializers.CharField()
    sessions = PlanSessionItemSerializer(many=True)


class PlanScreenResponseSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    title = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    status = UppercaseTokenField()
    total_sessions = serializers.IntegerField()
    assigned_players_count = serializers.IntegerField()
    assigned_players = PlanAssignedPlayerSerializer(many=True)
    training_sessions = PlanSessionGroupSerializer(many=True)


class TrainingPlanCreateResultSerializer(serializers.Serializer):
    message = serializers.CharField()
    plan = TrainingPlanDetailSerializer()
    sessions = TrainingSessionSerializer(many=True)
    assigned_player_ids = serializers.ListField(child=serializers.UUIDField())


class AssignPlayersSerializer(serializers.Serializer):
    player_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=True)

