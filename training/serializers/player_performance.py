from rest_framework import serializers


class PlayerPerformanceSessionsSerializer(serializers.Serializer):
    completed = serializers.IntegerField()
    planned = serializers.IntegerField()
    percentage = serializers.IntegerField()


class PlayerPerformanceEffortSerializer(serializers.Serializer):
    percentage = serializers.IntegerField()
    source = serializers.CharField()


class PlayerPerformanceRecoverySerializer(serializers.Serializer):
    percentage = serializers.IntegerField()
    source = serializers.CharField()


class PlayerPerformanceConsistencySerializer(serializers.Serializer):
    percentage = serializers.IntegerField()
    streak_days = serializers.IntegerField()


class PlayerPerformanceChartItemSerializer(serializers.Serializer):
    date = serializers.DateField()
    score = serializers.IntegerField()
    sessions = PlayerPerformanceSessionsSerializer()
    effort = PlayerPerformanceEffortSerializer()
    recovery = PlayerPerformanceRecoverySerializer()
    consistency = PlayerPerformanceConsistencySerializer()


class PlayerPerformanceSerializer(serializers.Serializer):
    days = PlayerPerformanceChartItemSerializer(many=True)
