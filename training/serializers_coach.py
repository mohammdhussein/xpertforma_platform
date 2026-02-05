from rest_framework import serializers
from training.models import TrainingPlan, TrainingSession, TrainingPlanPlayer

class TrainingPlanCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingPlan
        fields = ["plan_id", "title", "start_date", "end_date"]
        read_only_fields = ["plan_id"]

class TrainingPlanDetailSerializer(serializers.ModelSerializer):
    total_sessions = serializers.IntegerField(read_only=True)
    assigned_players = serializers.IntegerField(read_only=True)

    class Meta:
        model = TrainingPlan
        fields = ["plan_id", "title", "start_date", "end_date", "status", "total_sessions", "assigned_players"]

class SessionCreateSerializer(serializers.Serializer):
    # NOTE: no session_date here
    title = serializers.CharField(max_length=120, required=False, allow_blank=True)
    start_time = serializers.TimeField(required=False, allow_null=True)
    end_time = serializers.TimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)

class TrainingSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingSession
        fields = ["session_id", "plan", "session_date", "title", "start_time", "end_time", "notes"]
        read_only_fields = ["session_id", "plan", "session_date"]

class AssignPlayersSerializer(serializers.Serializer):
    player_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=True)
