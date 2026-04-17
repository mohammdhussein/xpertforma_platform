from rest_framework import serializers

from training.models import PlayerCheckin
from training.statuses import SleepQuality, VALID_SORE_ZONES


class SubmitCheckinSerializer(serializers.Serializer):
    sleep_hours   = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=24)
    sleep_quality = serializers.ChoiceField(choices=SleepQuality.choices)
    mood          = serializers.IntegerField(min_value=1, max_value=5)
    sore_zones    = serializers.ListField(
        child=serializers.ChoiceField(choices=VALID_SORE_ZONES),
        allow_empty=True,
    )


class CheckinDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PlayerCheckin
        fields = [
            "id",
            "player_id",
            "date",
            "sleep_hours",
            "sleep_quality",
            "mood",
            "sore_zones",
            "readiness_score",
            "created_at",
        ]


class TodayStatusSerializer(serializers.Serializer):
    submitted = serializers.BooleanField()
    checkin   = CheckinDetailSerializer(allow_null=True)
