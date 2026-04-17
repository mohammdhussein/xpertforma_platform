from rest_framework import serializers


class ReadinessSerializer(serializers.Serializer):
    score           = serializers.IntegerField(allow_null=True)
    label           = serializers.CharField(allow_null=True)
    sleep_hours     = serializers.FloatField(allow_null=True)
    sleep_quality   = serializers.CharField(allow_null=True)
    mood            = serializers.IntegerField(allow_null=True)
    sore_zones      = serializers.ListField(child=serializers.CharField())
    submitted_today = serializers.BooleanField()


class UpcomingSessionSerializer(serializers.Serializer):
    id               = serializers.UUIDField()
    title            = serializers.CharField()
    session_date     = serializers.DateField()
    start_time       = serializers.TimeField(allow_null=True)
    duration_minutes = serializers.IntegerField(allow_null=True)
    intensity        = serializers.CharField()
    location         = serializers.CharField()
    squad_size       = serializers.IntegerField(allow_null=True)
    coach_note       = serializers.CharField()
    is_today         = serializers.BooleanField()


class WeeklyProgressSerializer(serializers.Serializer):
    distance_km        = serializers.FloatField()
    distance_km_prev   = serializers.FloatField(allow_null=True)
    distance_delta_pct = serializers.IntegerField(allow_null=True)
    load_ratio         = serializers.FloatField(allow_null=True)
    acute_load         = serializers.IntegerField()
    chronic_load       = serializers.IntegerField()
    load_status        = serializers.CharField()
    sessions_completed = serializers.IntegerField()
    sessions_planned   = serializers.IntegerField()
    streak_days        = serializers.IntegerField()
    top_sprint_kmh     = serializers.FloatField(allow_null=True)
    top_sprint_pb_kmh  = serializers.FloatField(allow_null=True)


class AIInsightSerializer(serializers.Serializer):
    tag  = serializers.CharField()
    text = serializers.CharField()


class PlayerHomeSerializer(serializers.Serializer):
    readiness         = ReadinessSerializer()
    upcoming_sessions = UpcomingSessionSerializer(many=True)
    weekly_progress   = WeeklyProgressSerializer()
    ai_insights       = AIInsightSerializer(many=True)
