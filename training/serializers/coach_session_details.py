from rest_framework import serializers

from xpertforma_platform.api_fields import UppercaseTokenField
from training.serializers.training_plans import SessionLifecycleDetailsSerializer


class CoachSessionPlanSummarySerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    title = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    status = UppercaseTokenField()


class CoachSessionDetailsSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    plan = CoachSessionPlanSummarySerializer()
    title = serializers.CharField()
    session_type = UppercaseTokenField()
    session_date = serializers.DateField()
    start_time = serializers.TimeField(allow_null=True)
    end_time = serializers.TimeField(allow_null=True)
    intensity = UppercaseTokenField()
    location = serializers.CharField(allow_blank=True)
    notes = serializers.CharField(allow_blank=True)
    status = UppercaseTokenField()
    lifecycle = SessionLifecycleDetailsSerializer()
