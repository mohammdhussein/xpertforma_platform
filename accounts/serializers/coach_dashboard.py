from rest_framework import serializers

from xpertforma_platform.api_fields import UppercaseTokenField


class TotalPlayersStatSerializer(serializers.Serializer):
    value = serializers.IntegerField()
    delta_value = serializers.IntegerField()


class SessionsTodayStatSerializer(serializers.Serializer):
    value = serializers.IntegerField()
    completed_count = serializers.IntegerField()
    next_start_time = serializers.CharField(allow_null=True)
    progress_percent = serializers.IntegerField()


class AttendanceWeekStatSerializer(serializers.Serializer):
    value_percent = serializers.IntegerField(allow_null=True)
    delta_percent = serializers.IntegerField(allow_null=True)


class AttentionStatSerializer(serializers.Serializer):
    value = serializers.IntegerField()
    progress_percent = serializers.IntegerField()


class OverviewStatsSerializer(serializers.Serializer):
    total_players = TotalPlayersStatSerializer()
    sessions_today = SessionsTodayStatSerializer()
    attendance_week = AttendanceWeekStatSerializer()
    attention = AttentionStatSerializer()


class AlertRelatedPlayerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    avatar_url = serializers.CharField(allow_null=True)


class AlertRelatedSessionSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    plan_id = serializers.UUIDField()
    title = serializers.CharField()
    session_date = serializers.DateField()
    start_time = serializers.TimeField(allow_null=True)


class AlertRelatedPlanSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    title = serializers.CharField()


class AlertSerializer(serializers.Serializer):
    id = serializers.CharField()
    severity = UppercaseTokenField()
    alert_type = UppercaseTokenField()
    title = serializers.CharField()
    description = serializers.CharField()
    related_players = AlertRelatedPlayerSerializer(many=True)
    related_session = AlertRelatedSessionSerializer(allow_null=True)
    related_plan = AlertRelatedPlanSerializer(allow_null=True)
    occurred_at = serializers.DateTimeField()


class AssignedPlayerSerializer(serializers.Serializer):
    id = serializers.UUIDField()


class CoachUpcomingSessionSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    plan_id = serializers.UUIDField()
    title = serializers.CharField()
    session_date = serializers.DateField()
    start_time = serializers.TimeField(allow_null=True)
    end_time = serializers.TimeField(allow_null=True)
    location = serializers.CharField(allow_blank=True)
    assigned_players = AssignedPlayerSerializer(many=True)
    session_type = UppercaseTokenField()
    players_count = serializers.IntegerField()


class CoachDashboardSerializer(serializers.Serializer):
    overview_stats = OverviewStatsSerializer()
    alerts = AlertSerializer(many=True)
    alerts_total = serializers.IntegerField()
    upcoming_sessions = CoachUpcomingSessionSerializer(many=True)
