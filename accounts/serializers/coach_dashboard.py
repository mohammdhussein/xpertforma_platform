from rest_framework import serializers

from accounts.serializers.position import PositionSummarySerializer
from xpertforma_platform.api_fields import UppercaseTokenField


class CoachDashboardStatsSerializer(serializers.Serializer):
    total_players = serializers.IntegerField()
    sessions_this_week = serializers.IntegerField()
    sessions_this_month = serializers.IntegerField()


class CoachDashboardPlayerCardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    position = PositionSummarySerializer()
    last_activity = serializers.DateTimeField(allow_null=True)
    avatar_url = serializers.CharField(allow_null=True)


class CoachUpcomingSessionSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    plan_id = serializers.UUIDField()
    title = serializers.CharField()
    session_date = serializers.DateField()
    start_time = serializers.TimeField(allow_null=True)
    session_type = UppercaseTokenField()
    players_count = serializers.IntegerField()
    duration_min = serializers.IntegerField()


class CoachDashboardSerializer(serializers.Serializer):
    stats = CoachDashboardStatsSerializer()
    my_players = CoachDashboardPlayerCardSerializer(many=True)
    upcoming_sessions = CoachUpcomingSessionSerializer(many=True)
