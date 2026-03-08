from rest_framework import serializers


class PlayerDashboardSessionSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    plan_id = serializers.UUIDField()
    title = serializers.CharField()
    session_date = serializers.DateField()
    start_time = serializers.TimeField(allow_null=True)
    end_time = serializers.TimeField(allow_null=True)
    duration_min = serializers.IntegerField()
    status = serializers.CharField()


class MacroProgressSerializer(serializers.Serializer):
    current_g = serializers.IntegerField()
    target_g = serializers.IntegerField()


class NutritionSummarySerializer(serializers.Serializer):
    calories_remaining = serializers.IntegerField()
    calories_goal = serializers.IntegerField()
    protein = MacroProgressSerializer()
    carbs = MacroProgressSerializer()
    fats = MacroProgressSerializer()


class WeeklyOverviewPointSerializer(serializers.Serializer):
    day_label = serializers.CharField()
    value = serializers.IntegerField()


class WeeklyOverviewSerializer(serializers.Serializer):
    percent_change_vs_last_week = serializers.IntegerField()
    is_up = serializers.BooleanField()
    series = WeeklyOverviewPointSerializer(many=True)
    today_label = serializers.CharField()
    today_value = serializers.IntegerField()
    average_value = serializers.IntegerField()


class PlayerDashboardSerializer(serializers.Serializer):
    session = PlayerDashboardSessionSerializer(allow_null=True)
    nutrition = NutritionSummarySerializer()
    weekly_overview = WeeklyOverviewSerializer()

