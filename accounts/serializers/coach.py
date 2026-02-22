from rest_framework import serializers


class PlayerCardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    position = serializers.CharField(allow_blank=True)
    state = serializers.CharField()               # active / needs_review / injured
    plan_chips = serializers.ListField(child=serializers.CharField())
    more_plans_count = serializers.IntegerField()


class PlayerListResponseSerializer(serializers.Serializer):
    counts = serializers.DictField(child=serializers.IntegerField())
    results = PlayerCardSerializer(many=True)
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()


class PlanProgressSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    title = serializers.CharField()
    started_at = serializers.DateField()
    status = serializers.CharField()  # active / completed
    overall_progress_percent = serializers.IntegerField()
    completed_sessions = serializers.IntegerField()
    remaining_sessions = serializers.IntegerField()


class PlayerHeaderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    age = serializers.IntegerField(allow_null=True)
    position = serializers.CharField(allow_blank=True)


class PlayerTrainingProgressResponseSerializer(serializers.Serializer):
    player = PlayerHeaderSerializer()
    plans = PlanProgressSerializer(many=True)