from rest_framework import serializers
from training.models import TrainingPlan, TrainingSession, TrainingPlanPlayer

class PlayerTrainingPlanSerializer(serializers.ModelSerializer):
    assigned_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = TrainingPlan
        fields = ["plan_id", "title", "description", "duration_days", "difficulty", "assigned_at"]


class PlayerTrainingSessionSerializer(serializers.ModelSerializer):
    plan = serializers.SerializerMethodField()

    class Meta:
        model = TrainingSession
        fields = [
            "session_id",
            "title",
            "session_date",
            "start_time",
            "end_time",
            "notes",
            "plan",
        ]

    def get_plan(self, obj):
        return {
            "plan_id": str(obj.plan.plan_id),
            "title": obj.plan.title,
        }
